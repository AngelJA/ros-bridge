import time
from cyber_py import cyber
from modules.canbus.proto.chassis_pb2 import Chassis
from modules.prediction.proto.prediction_obstacle_pb2 import PredictionObstacles

cyber.init('test')
node = cyber.Node('test')
msg = Chassis()
writer = node.create_writer('/apollo/canbus/chassis', type(msg))
msg.driving_mode = 1
msg.speed_mps = 0
msg.throttle_percentage = 0
msg.brake_percentage = 0
msg.engine_started = 1
msg.gear_location = 0

msg2 = PredictionObstacles()
writer2 = node.create_writer('/apollo/prediction', type(msg2))

while not cyber.is_shutdown():
    time.sleep(0.2)
    writer.write(msg)
    writer2.write(msg2)
