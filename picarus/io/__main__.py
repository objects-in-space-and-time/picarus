import hadoopy
import os
import picarus
import hashlib
import cStringIO as StringIO
import shutil
import tempfile


def _lf(fn):
    from . import __path__
    return os.path.join(__path__[0], fn)


def _sha1(fn, chunk_size=1048576):
    h = hashlib.sha1()
    data = open(fn)
    while 1:
        chunk = data.read(chunk_size)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def _record_to_file(v, out_path):
    """Get data from a record 'v' and store it in out_path

    Args:
        v: record
        out_path: Local output path
    """
    fp = _record_to_fp(v)
    try:
        shutil.move(fp.name, out_path)
    except AttributeError:
        with open(out_path, 'wb') as fp_out:
            fp_out.write(fp.read())


class _DelFile(file):

    def __init__(self, fn, *args, **kw):
        super(_DelFile, self).__init__(fn, *args, **kw)
        self._fn = fn

    def close(self, *args, **kw):
        super(_DelFile, self).close(*args, **kw)
        os.remove(self._fn)

        
def _record_to_fp(v):
    """Get data from a record 'v' and return a file object to it

    Args:
        v: record

    Returns:
        File object (either a NamedTemporaryFile or StringIO)
    """
    try:
        val = v['data']
        if not val:  # Empty data
            raise KeyError
        return StringIO.StringIO(val)
    except KeyError:
        try:
            fn = tempfile.NamedTemporaryFile().name
            hadoopy.get(v['hdfs_path'], fn)
            fp = _DelFile(fn)
            return fp
        except KeyError:
            raise ValueError("Can't find data or hdfs_path in record,"
                             " at least one is required.")


def _read_files(fns, prev_hashes, hdfs_output, output_format, max_record_size):
    """
    Args:
        fns: Iterator of file names
        prev_hashes: Set of hashes (they will be skipped), this is used to make
            the data unique

    Yields:
        Tuple of (data_hash, data) where data_hash is a sha1 hash
    """
    for fn in fns:
        sha1_hash = _sha1(fn)
        if sha1_hash not in prev_hashes:
            prev_hashes.add(sha1_hash)
            if output_format == 'record' and max_record_size is not None and max_record_size < os.stat(fn)[6]:
                # Put the file into the remote location
                hdfs_path = hadoopy.abspath('%s/_blobs/%s_%s' % (hdfs_output, sha1_hash, os.path.basename(fn)))
                data = ''
                hadoopy.put(fn, hdfs_path)
            else:
                hdfs_path = ''
                data = open(fn).read()
            if output_format == 'kv':
                yield sha1_hash, data
            elif output_format == 'record':
                out = {'sha1': sha1_hash, 'full_path': fn,
                       'extension': os.path.splitext(fn)[1][1:]}
                if data:
                    out['data'] = data
                if hdfs_path:
                    out['hdfs_path'] = hdfs_path
                yield sha1_hash, out


def load_local(local_input, hdfs_output, output_format='kv', max_record_size=None, max_kv_per_file=None, **kw):
    """Read data, de-duplicate, and put on HDFS in the specified format

    Args:
        local_input: Local directory path
        hdfs_output: HDFS output path
        output_format: One of 'kv' or 'record'.  If 'kv' then output sequence
            files of the form (sha1_hash, binary_file_data).  If 'record'
            then output sequence files of the form (sha1_hash, metadata)
            where metadata has keys
            sha1: Sha1 hash
            extension: File extension without a period (blah.avi -> avi,
                blah.foo.avi -> avi, blah -> '')
            full_path: Local file path
            hdfs_path: HDFS path of the file (if any), the data should be the
                binary contents of the file stored at this location on HDFS.
            data: Binary file contents

            where only one of data or hdfs_path has to exist.
        max_record_size: If using 'record' and the filesize (in bytes) is larger
            than this, then store the contents of the file in a directory called
            '_blobs' inside output path with the name as the sha1 hash prefixed
            to the original file name (example, hdfs_output/blobs/sha1hash_origname).
            If None then there is no limit to the record size (default is None).
        max_kv_per_file: If not None then only put this number of kv pairs in each
            sequence file (default None).
    """
    fns = sorted([os.path.join(local_input, x) for x in os.listdir(local_input)])
    if output_format not in ('kv', 'record'):
        raise ValueError('Unsupported output_format [%s]' % output_format)
    out = []
    out_cnt = 0
    for x in _read_files(fns, set(), hdfs_output, output_format, max_record_size):
        out.append(x)
        if max_kv_per_file is not None and max_kv_per_file < len(out):
            hadoopy.writetb(hdfs_output + '/part-%.5d' % out_cnt, out)
            out_cnt += 1
            out = []
    if out:
        hadoopy.writetb(hdfs_output + '/part-%.5d' % out_cnt, out)


def dump_local(hdfs_input, local_output, extension='', **kw):
    """Read data from hdfs and store the contents as hash.ext

    Args:
        hdfs_input: HDFS input path in either 'kv' or 'record' format
        local_output: Local directory output path
        extension: Use this file extension if none available (kv format or
            record with missing extension) (default '')
    """
    try:
        os.makedirs(local_output)
    except OSError:
        pass
    for k, v in hadoopy.readtb(hdfs_input):
        if not isinstance(k, str):
            raise ValueError("Key must be a string. If you are reading data in 'record' form use the 'records' file and not the directory it is in.")
        if isinstance(v, dict):  # record
            try:
                extension = '.' + v['extension'] if v['extension'] else extension
            except KeyError:
                pass
            _record_to_file(v, os.path.join(local_output, k + extension))
        else:
            out_path = os.path.join(local_output, k + ('.' + extension if extension else ''))
            with open(out_path, 'wb') as fp:
                fp.write(v)


def run_record_to_kv(hdfs_input, hdfs_output, **kw):
    hadoopy.launch_frozen(hdfs_input, hdfs_output, _lf('record_to_kv.py'), reducer=None)


def run_kv_to_record(hdfs_input, hdfs_output, extension, base_path, **kw):
    hadoopy.launch_frozen(hdfs_input, hdfs_output, _lf('kv_to_record.py'), reducer=None,
                          cmdenvs=['EXTENSION=%s' % extension,
                                   'BASE_PATH=%s' % base_path])
