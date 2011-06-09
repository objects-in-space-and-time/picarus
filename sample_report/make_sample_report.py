import json
import random
import os
import argparse


def videos(vid_jsdir, vid_tdir):
    videojsnames = [x for x in sorted(os.listdir(vid_jsdir))
                    if os.path.splitext(x)[1] == '.js']

    videos = []
    for videojsname in videojsnames:
        with open('%s/%s' % (vid_jsdir, videojsname), 'r') as f:
            videos.append(json.load(f))

    return videos


def make_image(imagehash, category, make_faces):
    if not make_faces:
        faces = []
    else:
        num_faces = random.randint(1,2)

        def make_face():
            w,h = random.random()/3+.1, random.random()/3+.1
            x,y = random.random()/3+.5, random.random()/3+.5
            return ((x-w/2,y-h/2), (x+w/2,y+h/2))
        faces = [make_face() for _ in range(num_faces)]

    return {
        'hash': imagehash,
        'categories': [category],
        'video': [],
        'faces': faces,
        }


def random_clusters(imagedir, category, make_faces=False):
    """Creates a test mockup of random clusters from a folder of images
    Returns:
       clusters: a list of clusters that can be JSONified and passed to the
       html renderer
    """
    image_extensions = set(['jpg', 'png', 'jpeg', 'gif', 'ico'])
    local_images = [os.path.splitext(x)[0]
                    for x in sorted(os.listdir(imagedir))
                    if os.path.splitext(x)[1][1:] in image_extensions]
    local_images = [make_image(h, category, make_faces) for h in local_images]

    clusters = []

    n_clusters = max(int(random.normalvariate(6,2)),2)

    # TODO add cluster children to simulate HAC

    for i in range(n_clusters):
        n_images = random.randrange(4,7)
        n_size = random.randrange(40,60)
        cluster = {'all_images': random.sample(local_images, n_size),
                   'sample_images': random.sample(local_images, n_images),
                   'std': random.normalvariate(10.0,2.0),
                   'position': (random.random(), random.random()),
                   'size': n_size,
                   'children': []}
        clusters.append(cluster)
    return clusters


def make_sample_object(imagedir, videosjs, vid_tdir):
    obj = {
        'videos': videos(videosjs, vid_tdir),
        'graphics': random_clusters(imagedir, 'graphics'),
        'inappropriate': random_clusters(imagedir, 'inappropriate'),
        'indoor': random_clusters(imagedir, 'indoor'),
        'outdoor': random_clusters(imagedir, 'outdoor'),
        'objects': random_clusters(imagedir, 'objects'),
        'faces': random_clusters(imagedir, 'faces', make_faces=True),
        }
    return obj


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve images and features \
    from Cassandra")

    # Thumbnail images
    parser.add_argument('--thumbdir',
                       help='use images from this folder',
                       default='./t/')

    # Videojs folder
    parser.add_argument('--videosjs',
                       help='look for *.js video files in this folder',
                       default='./videojs/')

    # Video thumbnails folder
    parser.add_argument('--vid_tdir',
                       help='thumbnails for video frames',
                       default='./vid_t/')

    # Output js
    parser.add_argument('--outputjs',
                        default='sample_report.js')

    ARGS = parser.parse_args()

    obj = make_sample_object(ARGS.thumbdir,
                             ARGS.videosjs,
                             ARGS.vid_tdir)

    with open(ARGS.outputjs, 'w') as f:
        # Prepend a variable assignment so we can load this easier
        f.write('var report = ');

        # Write the actual json
        json.dump(obj, f, indent=2)
