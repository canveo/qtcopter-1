#!/usr/bin/env python
# Software License Agreement (BSD License)

import time
import rospy
from mavros.msg import OverrideRCIn
from mavros.srv import CommandBool, CommandLong
from mavros.srv import SetMode
from rospy.core import rospydebug
from threading import Thread
from RcMessage import RcMessage
from mavros.msg import State
from Configuration import Configuration
from geometry_msgs.msg import PoseWithCovarianceStamped
from mavros.msg import RCIn
from std_msgs.msg import Float64
from qtcopter.msg import controller_msg

config = Configuration("NavConfig.json")
#FlightMode class : encapsulates all mode related operations of the drone
#To be further implemented
class Navigator:
    __rcMessage = None
    __armingService = None
    __setModeService = None
    __rcOverrideTopic = None
    __humanOverrideFlag = False
    __humanOverrideDefault = None
    __humanOverrideElapsedTime = 0
    __navigatorParams = None
    __baseGlobalPosition = None
    __currentGlobalPosition = None
    __currentMode = None

    #Register to all needed topics/services for this object
    #init a RcMessage as a member for this class, to be able to control whats published
    #on the rc/override topic
    def __init__(self):
        self.__navigatorParams = config.GetConfigurationSection("params")
        self.__humanOverrideDefault = self.__navigatorParams["HumanOverrideDefault"]
        self.__setModeService = rospy.Service('navigator/set_mode', SetMode, self.__SetCurrentMode)
        self.__armingService = rospy.ServiceProxy('/mavros/cmd/arming', CommandBool)
        self.__setModeMavros = rospy.ServiceProxy('/mavros/set_mode',SetMode)
        self.__rcOverrideTopic = rospy.Publisher('/mavros/rc/override',OverrideRCIn,queue_size = 10) #TBD : how to determine queue size
        self.__rcInListener = rospy.Subscriber('/mavros/rc/in',RCIn,self.__HumanOverrideCallback)
        self.__rcMessage = RcMessage()
        self.__isArmed = False
        self.__IsPublishAllowedBool = True
        self.__rcMessage.ResetRcChannels()
        self.__rcOverrideTopic.publish(self.__rcMessage.GetRcMessage())

    #Arm: arm/disarm the drone
    #param : armDisarmBool - true for arm, false for disarm
    #return value : success/failure
    def Arm(self, armDisarmBool):
        self.__baseGlobalPosition = self.__currentGlobalPosition
        self.__rcMessage.PrepareForArming()
        self.__rcOverrideTopic.publish(self.__rcMessage.GetRcMessage())
        time.sleep(1) #TBD : is this necessary? need to check if topic was grabbed
        try:
            self.__armingService(armDisarmBool)
            self.__isArmed = True
        except rospy.ServiceException as ex:
            print("Service did not process request: " + str(ex))
            return False

    #ConstantRatePublish : publishing the outputs of pid_controller to rc_override channels
    #at 25hz rate.
    #runs as a separate thread so the set_mode service won't be occupied.
    def __ConstantRatePublish(self, arg):
        print "DEBUG: ConstantRatePublish Started" + self.__currentMode.upper()
        rate = rospy.Rate(self.__navigatorParams["PublishRate"])
        while self.__currentMode.upper() == 'PID_ACTIVE' or self.__currentMode.upper() == 'PID_ACTIVE_HOLD_ALT':
            print str(self.__IsPublishAllowedBool)
            if self.__IsPublishAllowedBool:
                stime = time.time()
                try:
                    msg = rospy.wait_for_message('/pid/controller_command',controller_msg)
                    self.PublishRCMessage(msg.x, msg.y, msg.z, msg.t)
                    rate.sleep()
                    etime = time.time()
                    print("publishing : {0} {1} {2} {3} elapsed:{4}".format(msg.x,msg.y,msg.z,msg.t,etime - stime))
                except:
                    print "ERROR : controller msg from pid topic did not process"
            else:
                print "Human override activated, publishing thread stopping..."
                break
        return 1

    #SetCurrentMode : set the current mode of flight (navigator/set_mode callback)
    #activated by calling 'navigator/set_mode' service with with mode and additional param
    #params : mode - the requested mode of flight as SetMode
    #return value : success/failure
    def __SetCurrentMode(self, mode):
        try:
            srv = rospy.ServiceProxy('/mavros/set_mode',SetMode)
        except rospy.ServiceException as ex:
            print("Service did not process request: " + str(ex))
            return False

        self.__currentMode = mode.custom_mode
        var = mode.custom_mode.upper()
        if var == 'ARM':
            self.__setModeMavros(base_mode=0, custom_mode='STABILIZE')
            self.Arm(True)
        elif var == 'DISARM':
            self.__setModeMavros(base_mode=0, custom_mode='STABILIZE')
            self.Arm(False)
        elif var == 'ALT_HOLD':
            srv(base_mode=0, custom_mode='ALT_HOLD')
        elif var == 'TAKEOFF':
            self.__setModeMavros(base_mode=0, custom_mode='STABILIZE')
            thread = Thread(target = self.__PerformTakeoff, args = (int(mode.base_mode), ))
            thread.start()
        elif var == 'LAND':
            self.__setModeMavros(base_mode=0, custom_mode='LAND')
            self.__isArmed = False
        elif var == 'STABILIZE':
            srv(base_mode=0, custom_mode='STABILIZE')
        elif var == 'PID_ACTIVE':
            self.__setModeMavros(base_mode=0, custom_mode='STABILIZE')
            thread = Thread(target = self.__ConstantRatePublish, args = (int(mode.base_mode), ))
            thread.start()
        elif var == 'PID_ACTIVE_HOLD_ALT':
            self.__setModeMavros(base_mode=0, custom_mode='ALT_HOLD')
            thread = Thread(target = self.__ConstantRatePublish, args = (int(mode.base_mode), ))
            thread.start()
        elif var == 'PID_RESET':
            #TODO: reset pid logic here
            print "to be implemented"

        print "Navigator is changing flight mode"
        print "mode: " + self.__currentMode.upper()
        return True

    #PublishRCMessage : publish new message to rc/override topic to set rc channels
    #params : roll, pitch, throttle, yaw as integer values between 1000 to 2000
    def PublishRCMessage(self, roll, pitch, throttle, yaw):
        if self.__IsPublishAllowed():
            self.__rcMessage.SetRoll(roll)
            self.__rcMessage.SetPitch(pitch)
            self.__rcMessage.SetThrottle(throttle)
            self.__rcMessage.SetYaw(yaw)
            self.__rcOverrideTopic.publish(self.__rcMessage.GetRcMessage())

    #HumanOverrideCallback : Constantly checking rc/override HumanOverride channel and maintaining a
    #boolean flag according to that
    def __HumanOverrideCallback(self, data):
        self.__humanOverrideElapsedTime = time.time()
        val = data.channels[self.__navigatorParams["HumanOverrideChannel"]]
        threshHold = self.__navigatorParams["HumanOverrideThreshold"]
        if (val < self.__humanOverrideDefault - threshHold) or (val > self.__humanOverrideDefault + threshHold):
            self.__humanOverrideFlag = True
        #else:
            #self.__humanOverrideFlag = False

    #IsPublishAllowed : Make all safety checks in this method.
    #return value : True/False according to all safety checks.
    def __IsPublishAllowed(self):
        #TODO: break if statment into two scenarios:
        #1. LAND
        #2. STABILIZE
        if self.__humanOverrideFlag or self.__humanOverrideElapsedTime != 0 and \
                (time.time() - self.__humanOverrideElapsedTime > self.__navigatorParams["HumanOverrideElapsedTimeAllowed"]):
            self.__rcMessage.ResetRcChannels()
            self.__rcOverrideTopic.publish(self.__rcMessage.GetRcMessage())
            self.__setModeMavros(base_mode=0, custom_mode='STABILIZE')
            self.__IsPublishAllowedBool = False
            print "DEBUG: (IsPublishAllowed):Human override channel activated, publish disabled"
            #TBD: define logger behavior here
            return False
        else:
            #self.__IsPublishAllowedBool = True
            return True

if __name__ == '__main__':
    try:
        rospy.init_node('Navigator', anonymous=True)
        nav = Navigator()
        while not rospy.is_shutdown():
            time.sleep(0)
    except rospy.ROSInterruptException:
        pass







