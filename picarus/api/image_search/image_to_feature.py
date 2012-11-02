#!/usr/bin/env python
import hadoopy
import imfeat
import os
from hbase_mapper import HBaseMapper
import picarus.api


class Mapper(HBaseMapper):

    def __init__(self):
        super(Mapper, self).__init__()
        self._feat = picarus.api.model_fromfile(os.environ['FEATURE_FN'])

    def _map(self, row, image_binary):
        try:
            image = imfeat.image_fromstring(image_binary)
            yield row, picarus.api.np_tostring(self._feat(image))
        except:
            hadoopy.counter('DATA_ERRORS', 'ImageLoadError')


if __name__ == '__main__':
    hadoopy.run(Mapper, required_cmdenvs=['HBASE_INPUT_COLUMN', 'HBASE_TABLE', 'HBASE_OUTPUT_COLUMN', 'FEATURE_FN'])
