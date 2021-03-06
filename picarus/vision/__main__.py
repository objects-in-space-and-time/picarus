import hadoopy
import viderator
import os
import picarus
import glob
import tempfile
import imfeat
import cPickle as pickle
import base64
import zlib
import json
from picarus import _file_parse as file_parse


def _lf(fn):
    from . import __path__
    return os.path.join(__path__[0], fn)


def run_image_feature(hdfs_input, hdfs_output, feature, files=(), **kw):
    files = list(files)
    if isinstance(feature, dict):
        feature = zlib.compress(json.dumps(feature), 9)
    feature_fp = tempfile.NamedTemporaryFile()
    feature_fp.write(feature)
    feature_fp.flush()
    # This allows for replacing the default models
    cur_files = set([os.path.basename(x) for x in files])
    for x in [_lf('data/hog_8_2_clusters.pkl'), _lf('data/eigenfaces_lfw_cropped.pkl')] + glob.glob(imfeat.__path__[0] + "/_object_bank/data/*"):
        if os.path.basename(x) not in cur_files:
            files.append(x)
            cur_files.add(x)
    files.append(feature_fp.name)
    picarus._launch_frozen(hdfs_input, hdfs_output, _lf('feature_compute.py'),
                           cmdenvs=['FEATURE=%s' % os.path.basename(feature_fp.name)],
                           files=files,
                           dummy_arg=feature_fp, **kw)


def run_image_clean(hdfs_input, hdfs_output, max_side=None, filter_side=None, **kw):
    cmdenvs = {}
    if max_side is not None:
        cmdenvs['MAX_SIDE'] = max_side
    if filter_side is not None:
        cmdenvs['FILTER_SIDE'] = filter_side
    picarus._launch_frozen(hdfs_input, hdfs_output, _lf('image_clean.py'),
                           cmdenvs=cmdenvs, **kw)


def run_image_feature_point(hdfs_input, hdfs_output, feature, image_length=None, image_height=None, image_width=None, **kw):
    if image_length:
        image_height = image_width = image_length
    if image_height is None or image_width is None:
        raise ValueError('Please specify image_height/image_width or image_length')
    picarus._launch_frozen(hdfs_input, hdfs_output, _lf('feature_point_compute.py'),
                           cmdenvs=['IMAGE_HEIGHT=%d' % image_height,
                                    'IMAGE_WIDTH=%d' % image_width,
                                    'FEATURE=%s' % feature],
                           files=[_lf('data/eigenfaces_lfw_cropped.pkl')] + glob.glob(imfeat.__path__[0] + "/_object_bank/data/*"))


def run_face_finder(hdfs_input, hdfs_output, image_length, boxes, image_hashes=None, **kw):
    cmdenvs = ['IMAGE_LENGTH=%d' % image_length]
    if boxes:
        cmdenvs.append('OUTPUT_BOXES=True')
    picarus._launch_frozen(hdfs_input, hdfs_output, _lf('face_finder.py'), reducer=None,
                           cmdenvs=cmdenvs,
                           files=[_lf('data/haarcascade_frontalface_default.xml')],
                           image_hashes=image_hashes)


def run_predict_windows(hdfs_input, hdfs_classifier_input, feature, hdfs_output, image_height, image_width, **kw):
    import classipy
    # NOTE: Adds necessary files
    files = glob.glob(classipy.__path__[0] + "/lib/*")
    fp = tempfile.NamedTemporaryFile(suffix='.pkl.gz')
    file_parse.dump(list(hadoopy.readtb(hdfs_classifier_input)), fp.name)
    files.append(fp.name)
    files.append(_lf('data/haarcascade_frontalface_default.xml'))
    cmdenvs = ['CLASSIFIERS_FN=%s' % os.path.basename(fp.name)]
    cmdenvs += ['IMAGE_HEIGHT=%d' % image_height,
                'IMAGE_WIDTH=%d' % image_width,
                'FEATURE=%s' % feature]
    picarus._launch_frozen(hdfs_input, hdfs_output, _lf('predict_windows.py'),
                           cmdenvs=cmdenvs,
                           files=files,
                           dummy_arg=fp)


def run_video_keyframe(hdfs_input, hdfs_output, frame_skip=1, min_interval=5, max_interval=float('inf'), max_time=float('inf'), keyframer='uniform', **kw):
    fp = viderator.freeze_ffmpeg()
    picarus._launch_frozen(hdfs_input, hdfs_output + '/keyframe', _lf('video_keyframe.py'),
                           cmdenvs=['MIN_INTERVAL=%f' % min_interval,
                                    'MAX_INTERVAL=%f' % max_interval,
                                    'FRAME_SKIP=%d' % frame_skip,
                                    'KEYFRAMER=%s' % keyframer,
                                    'MAX_TIME=%f' % max_time],
                           jobconfs=['mapred.child.java.opts=-Xmx768M',
                                     'mapred.task.timeout=12000000',
                                     'mapred.map.max.attempts=10'],
                           files=[fp.__enter__()],
                           dummy_arg=fp)


def run_video_grep_frames(hdfs_input, hdfs_output, feature, max_frames_per_video=None, max_outputs_per_video=None, output_frame=True, **kw):
    fp = viderator.freeze_ffmpeg()
    feature_fp = tempfile.NamedTemporaryFile(suffix='.pkl')
    pickle.dump(feature, feature_fp, -1)
    feature_fp.flush()
    cmdenvs = ['FEATURE_FN=%s' % os.path.basename(feature_fp.name)]
    if max_frames_per_video is not None:
        cmdenvs.append('MAX_FRAMES_PER_VIDEO=%d' % (max_frames_per_video))
    if max_outputs_per_video is not None:
        cmdenvs.append('MAX_OUTPUTS_PER_VIDEO=%d' % (max_outputs_per_video))
    cmdenvs.append('OUTPUT_FRAME=%d' % int(output_frame))
    picarus._launch_frozen(hdfs_input, hdfs_output, _lf('video_grep_frames.py'),
                           cmdenvs=cmdenvs,
                           jobconfs=['mapred.child.java.opts=-Xmx512M',
                                     'mapred.task.timeout=12000000',
                                     'mapred.map.max.attempts=10'],
                           files=[fp.__enter__(), feature_fp.name],
                           dummy_arg=(fp, feature_fp))


def run_video_max_conf_frames(hdfs_input, hdfs_output, feature, max_frames_per_video=None, max_outputs=None, output_frame=True, **kw):
    fp = viderator.freeze_ffmpeg()
    feature_fp = tempfile.NamedTemporaryFile(suffix='.pkl')
    pickle.dump(feature, feature_fp, -1)
    feature_fp.flush()
    cmdenvs = ['FEATURE_FN=%s' % os.path.basename(feature_fp.name)]
    if max_frames_per_video is not None:
        cmdenvs.append('MAX_FRAMES_PER_VIDEO=%d' % (max_frames_per_video))
    if max_outputs is not None:
        cmdenvs.append('MAX_OUTPUTS=%d' % (max_outputs))
    cmdenvs.append('OUTPUT_FRAME=%d' % int(output_frame))
    cmdenvs.append('PYTHONUNBUFFERED=true')
    picarus._launch_frozen(hdfs_input, hdfs_output, _lf('video_max_conf_frames.py'),
                           cmdenvs=cmdenvs,
                           jobconfs=['mapred.child.java.opts=-Xmx768M',
                                     'mapred.task.timeout=12000000',
                                     'mapred.map.max.attempts=10'],
                           files=[fp.__enter__(), feature_fp.name],
                           dummy_arg=(fp, feature_fp))


def run_video_predicate_frames(hdfs_input, hdfs_output, features, max_frames_per_video=None, **kw):
    fp = viderator.freeze_ffmpeg()
    features_fp = tempfile.NamedTemporaryFile(suffix='.pkl')
    pickle.dump(features, features_fp, -1)
    features_fp.flush()
    cmdenvs = ['FEATURES_FN=%s' % os.path.basename(features_fp.name)]
    if max_frames_per_video is not None:
        cmdenvs.append('MAX_FRAMES_PER_VIDEO=%d' % (max_frames_per_video))
    picarus._launch_frozen(hdfs_input, hdfs_output + '/predicate_frames', _lf('video_predicate_frames.py'),
                           cmdenvs=cmdenvs,
                           jobconfs=['mapred.child.java.opts=-Xmx768M',
                                     'mapred.skip.attempts.to.start.skipping=2',
                                     'mapred.skip.map.max.skip.records=1',
                                     'mapred.skip.mode.enabled=true',
                                     'mapred.skip.reduce.auto.incr.proc.count=false'
                                     'mapred.skip.map.auto.incr.proc.count=false',
                                     'mapred.task.timeout=12000000',
                                     'mapred.map.max.attempts=10'],
                           files=[fp.__enter__(), features_fp.name],
                           dummy_arg=(fp, features_fp))



def run_video_features(hdfs_input, hdfs_output, **kw):
    fp = viderator.freeze_ffmpeg()
    picarus._launch_frozen(hdfs_input, hdfs_output + '/features', _lf('video_combined_features.py'),
                           cmdenvs=[],
                           jobconfs=['mapred.child.java.opts=-Xmx512M',
                                     'mapred.task.timeout=12000000',
                                     'mapred.map.max.attempts=10'],
                           files=[fp.__enter__(), _lf('data/haarcascade_frontalface_default.xml')],
                           dummy_arg=fp)
