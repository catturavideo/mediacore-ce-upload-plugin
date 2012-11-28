import os
import logging
import string
import random
import json
import webob.exc
from cgi import FieldStorage
from functools import wraps
from sqlalchemy import orm, sql
from mediacore.lib.base import BaseController
from mediacore.lib.helpers import url_for
from mediacore.lib.decorators import expose, validate, autocommit
from mediacore.model import User, Author, Category, Media, MediaFile, Podcast, Tag, fetch_row, get_available_slug
from mediacore.model.meta import DBSession
from mediacore.lib.storage import StorageEngine

log = logging.getLogger(__name__)
upload_tokens = {}

def require_admin(action):
    """
    Decorator that enforces that valid admin credentials are presented through HTTP basic authentication.
    """
    @wraps(action)
    def func(*args,**kwargs):
        environ = kwargs['environ']
        if 'HTTP_AUTHORIZATION' not in environ:
            raise webob.exc.HTTPUnauthorized().exception
            
        method, credentials = environ['HTTP_AUTHORIZATION'].split(" ",2)
        if method.strip().lower() == 'basic':
            username, password = credentials.strip().decode('base64').split(":",2)
            user = DBSession.query(User).filter("user_name='{username}'".format(username=username)).first()
            if user is None or not user.has_permission('admin') or not user.validate_password(password):
                raise webob.exc.HTTPUnauthorized().exception
        else:
            raise webob.exc.HTTPUnauthorized().exception
            
        return action(*args,**kwargs)
    return func

def getStorageEngine():
    return DBSession.query(StorageEngine).filter("enabled = 1 and engine_type = 'LocalFileStorage'").first()

class UploaderController(BaseController):
    """
    Bulk Upload API
    """
    @require_admin
    @autocommit
    @expose("json",request_method="POST")
    def createMediaItem(self,title,author_email=None,author_name=None,slug=None,
                        tags=None,podcast_id=None,category_ids=None,meta=None,**kwargs):
        mediaItem = Media()
        log.info("createMediaItem({title})".format(title=title))
        
        if not slug:
            slug = title
        elif slug.startswith('_stub_'):
            slug = slug[len('_stub_'):]
        if slug != mediaItem.slug:
            mediaItem.slug = get_available_slug(Media, slug, mediaItem)
            
        if podcast_id:
            podcast_id = int(podcast_id)
        else:
            podcast_id = 0
        
        if not meta:
            meta = {}
        else:
            try:
                meta = json.loads(meta)
            except Exception as e:
                return {"success": False, "message": "Invalid JSON object given for `meta`"}
        
        mediaItem.title = title
        mediaItem.author = Author(author_name or "No Author", author_email or "No Email")
        mediaItem.podcast_id = podcast_id or None
        mediaItem.set_tags(tags)
        mediaItem.set_categories(category_ids)
        mediaItem.update_status()
        mediaItem.meta = meta
        
        DBSession.add(mediaItem)
        DBSession.flush()
        
        return {
            "success": True,
            "id": mediaItem.id
        }

    @require_admin
    @autocommit
    @expose("json",request_method="POST")
    def prepareForUpload(self,environ,media_id,content_type,filename,filesize,meta=None,**kwargs):        
        STORAGE_ENGINE = getStorageEngine()
        log.info("prepareForUpload({media_id},{content_type},{filename},{filesize})".format(**vars()))

        if not meta:
            meta = {}
        else:
            try:
                meta = json.loads(meta)
            except Exception as e:
                return {"success": False, "message": "Invalid JSON object given for `meta`"}

        media = fetch_row(Media, media_id)
        mediaFile = MediaFile()
        mediaFile.storage = STORAGE_ENGINE
        mediaFile.media = media
        mediaFile.media_id = media_id
        mediaFile.type = content_type
        mediaFile.meta = meta
        media.type = content_type
        mediaFile.display_name = filename
        mediaFile.size = filesize
        media.files.append(mediaFile)
        
        DBSession.add(media)
        DBSession.add(mediaFile)
        DBSession.flush()
        
        # This is to ensure that we don't allow any uploads that haven't been prepared for with prepareForUpload
        token = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(13))
        upload_tokens[str(mediaFile.id)] = token
                
        return {
            "success": True,
            "id": mediaFile.id,
            "upload_url": "http://{host}{path}".format(host=environ['HTTP_HOST'],path=url_for(controller='upload_api/api/uploader',action='uploadFile',media_id=media_id,file_id=mediaFile.id)),
            "upload_headers": {
                "Content-Type": "application/octet-stream",
                "Cache-Control": "none",
                "X-File-Name": filename,
                "X-Upload-Token": token
            },
            "postprocess_url": "http://{host}{path}".format(host=environ['HTTP_HOST'],path=url_for(controller='upload_api/api/uploader',action='postprocessFile',media_id=media_id,file_id=mediaFile.id))
        }

    @autocommit
    @expose("json",request_method="POST")
    def uploadFile(self,environ,media_id,file_id,**kwargs):
        log.info("uploadFile({media_id},{file_id})".format(**vars()))
        
        media = fetch_row(Media, media_id)
        mediaFile = fetch_row(MediaFile, file_id)

        # Requests not carrying a valid X-Upload-Token must be rejected immediately
        if 'HTTP_X_UPLOAD_TOKEN' not in environ or str(file_id) not in upload_tokens.keys():
            raise webob.exc.HTTPForbidden().exception
        elif not environ['HTTP_X_UPLOAD_TOKEN'] == upload_tokens[str(file_id)]:
            raise webob.exc.HTTPForbidden().exception            

        STORAGE_ENGINE = getStorageEngine()

        class FileEntry(object):
            def __init__(self,file,name=None):
                self.file = file
                self.filename = name if name else file.name

        unique_id = STORAGE_ENGINE.store(media_file=mediaFile, file=FileEntry(environ['wsgi.input'],mediaFile.display_name))

        try:
            STORAGE_ENGINE.transcode(mediaFile)
        except Exception:
            log.debug('Engine %r unsuitable for transcoding %r', STORAGE_ENGINE, mediaFile)            

        mediaFile.container = os.path.splitext(mediaFile.display_name)[1][1:]
        if unique_id:
            mediaFile.unique_id = unique_id

        DBSession.add(mediaFile)
        DBSession.flush()

        del upload_tokens[str(file_id)]

        # Ideally we'd determine information about the uploaded media file and return it here.
        return {}
        
    @require_admin
    @expose("json",request_method="PUT")
    def postprocessFile(self,media_id,file_id,**kwargs):
        log.info("postprocessFile({media_id},{file_id})".format(**vars()))
        return {
            "success": True
        }
