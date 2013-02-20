import json
import tempfile
import os

class UploadTokens(object):
    def __init__(self):
        self.filename = os.path.join(tempfile.gettempdir(),"mediacore-upload-tokens.txt")
        self.__load()

    def __setitem__(self,key,value):
        self.data[key] = value
        self.__save()

    def __delitem__(self,key):
        del self.data[key]
        self.__save()

    def __getitem__(self,key):
        return self.data[key]

    def __contains__(self,key):
        return key in self.data

    def keys(self):
        return self.data.keys()

    def __repr__(self):
        return repr(self.data)

    def __str__(self):
        return str(self.data)

    def __len__(self):
        return len(self.data)

    def __load(self):
        if os.path.exists(self.filename):
            with open(self.filename,'r') as data:
                self.data = json.loads(data.read())
        else:
            self.data = {}

    def __save(self):
        with open(self.filename,'w') as data:
            data.write(json.dumps(self.data))

upload_tokens = UploadTokens()
