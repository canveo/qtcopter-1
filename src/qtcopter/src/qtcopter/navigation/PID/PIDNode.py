#!/usr/bin/env python
# Software License Agreement (BSD License)


import rospy
from qtcopter.msg import controller_msg, uav_msg
from threading import Thread
from PIDModule import PIDModule
from PIDModule import PIDController
from ..Configuration import Configuration

config = Configuration("PidConfig.json")

class PIDManager:
    def __init__(self, dt, minLimit, maxLimit):
        xConfig = config.GetConfigurationSection("X")
        yConfig = config.GetConfigurationSection("Y")
        zConfig = config.GetConfigurationSection("Z")
        thetaConfig = config.GetConfigurationSection("Theta")
        self.AxisControllers = {"X": PIDController(xConfig["KP"], xConfig["KI"], xConfig["KD"], dt, minLimit, maxLimit),
                                "Y": PIDController(yConfig["KP"], yConfig["KI"], yConfig["KD"], rate, minLimit, maxLimit),
                                "Z": PIDController(zConfig["KP"], zConfig["KI"], zConfig["KD"], rate, minLimit, maxLimit),
                                "Theta": PIDController(thetaConfig["KP"], thetaConfig["KI"], thetaConfig["KD"], rate, minLimit, maxLimit)
                                }
        rospy.Subscriber("/ip/error", controller_msg, self.DataCollector)

    def DataCollector(self, msg):
        self.AxisControllers["X"].SetError(msg.X)
        self.AxisControllers["Y"].SetError(msg.Y)
        self.AxisControllers["Z"].SetError(msg.Z)
        self.AxisControllers["Theta"].SetError(msg.Theta)

    def Run(self):
        msg = controller_msg()
        msg.X = self.AxisControllers["X"].GetFix()
        msg.Z = self.AxisControllers["Z"].GetFix()
        msg.Y = self.AxisControllers["Y"].GetFix()
        msg.Theta = self.AxisControllers["Theta"].GetFix()
        return msg

if __name__ == '__main__':
    try:
        rospy.init_node('pid_node', anonymous=True)
        pid_publisher = rospy.Publisher('/pid/controller_command',controller_msg,queue_size=25)
        config = Configuration("PidConfig.json")
        generalConfig = config.GetConfigurationSection("General")
        pidManager = PIDManager(generalConfig["Rate"], generalConfig["MinLimit"], generalConfig["MaxLimit"])
        rate = rospy.Rate(generalConfig["Rate"])
        while not rospy.is_shutdown():
            fix = pidManager.Run()
            rate.sleep()
            pid_publisher.publish(fix)
    except rospy.ROSInterruptException:
        pass

# #PIDNode : Type for controlling several PIDModule instances.
# #A dedicated node will be instantiated and will live during the whole run.
# #A loop with constant rate will collect the data (deltas) from the vision control topic,
# #perform all calculations on it and publish the results to the drone navigation module.
# class PIDNode:
#     pid_output = None
#     pid_input = None
#
#     def __init__(self):
#         self.pid_input = controller_msg()
#         self.pid_output = controller_msg()
#         self.__InitWorkingThreads()
#
#     #InitWorkingThreads : A helper method for creating multiple threads
#     def __InitWorkingThreads(self):
#         x = Thread(target=self.__RunPIDModule1(self.pid_input.x,5,0.2,0.05))
#         x.start()
#         y = Thread(target=self.__RunPIDModule2(self.pid_input.y,5,0.2,0.05))
#         y.start()
#         z = Thread(target=self.__RunPIDModule3(self.pid_input.z,5,0.2,0.05))
#         z.start()
#
#     #RunPIDModule : For each thread a PIDModule instance is created and performs continuously
#     #PID calculations
#     #Params : input - delta in meters, Kp,Kd,Ki mathematical constants
#     def __RunPIDModule1(self,input, Kp, Kd, Ki):
#         pid_module = PIDModule(Kp,Kd,Ki)
#         while(1):
#             self.pid_output.x = pid_module.GetPIDValue(input)
#
#     def __RunPIDModule2(self,input, Kp, Kd, Ki):
#         pid_module = PIDModule(Kp,Kd,Ki)
#         while(1):
#             self.pid_output.y = pid_module.GetPIDValue(input)
#
#     def __RunPIDModule3(self,input, Kp, Kd, Ki):
#         pid_module = PIDModule(Kp,Kd,Ki)
#         while(1):
#             self.pid_outputs.z = pid_module.GetPIDValue(input)
#
# if __name__ == '__main__':
#     try:
#         rospy.init_node('pid_node', anonymous=True)
#         pid_publisher = rospy.Publisher('/pid/controller_command',controller_msg,queue_size=25)
#         pidNode = PIDNode() #one instance of PIDNode
#         rate = rospy.Rate(25) #TBD
#         while not rospy.is_shutdown():
#            vision_message = rospy.wait_for_message('/pid/vision_input',controller_msg) #TBD
#            pidNode.pid_input.x = vision_message.x
#            pidNode.pid_input.y = vision_message.y
#            pidNode.pid_input.z = vision_message.z
#            pid_publisher.publish(pidNode.pid_output)
#            rate.sleep()
#
#
#
#     except rospy.ROSInterruptException:
#         pass