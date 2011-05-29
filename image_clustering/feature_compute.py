import hadoopy
import imfeat
import Image
import cStringIO as StringIO


def mapper(name, image_data):
    try:
        image = Image.open(StringIO.StringIO(image_data))
    except:
        hadoopy.counter('DATA_ERRORS', 'ImageLoadError')
        return
    feat = imfeat.Histogram('rgb', style='joint')
    try:
        yield name, imfeat.compute(feat, image)[0]
    except ValueError:
        hadoopy.counter('DATA_ERRORS', 'UnkImageType')
        return


if __name__ == '__main__':
    hadoopy.run(mapper)