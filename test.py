import time
from cyber_py import cyber, cyber_time
from modules.prediction.proto.prediction_obstacle_pb2 import PredictionObstacles
from modules.transform.proto.transform_pb2 import TransformStamped, TransformStampeds

cyber.init('test')
node = cyber.Node('test')

tfs = TransformStampeds()
tf_writer = node.create_writer('/tf', type(tfs))

while not cyber.is_shutdown():
    if len(tfs.transforms):
        tf = tfs.transforms[0]
    else:
        tf = TransformStamped()
        tfs.transforms.append(tf)
    tf.header.timestamp_sec = cyber_time.Time.now().to_sec()
    tf.header.frame_id = 'novatel'
    tf.child_frame_id = 'world'
    tf.transform.translation.x = 1
    tf.transform.translation.y = 0
    tf.transform.translation.z = 0
    tf.transform.rotation.qx = 0
    tf.transform.rotation.qy = 0
    tf.transform.rotation.qz = 0
    tf.transform.rotation.qw = 0
    time.sleep(0.2)
    tf_writer.write(tfs)
