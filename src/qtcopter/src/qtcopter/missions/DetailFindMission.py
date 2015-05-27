import rospy
import smach
import smach_ros
from sensor_msgs.msg import Image
from qtcopter.missions import CoarseFind, DetailFind

"""
ROS node for qrcode scan mission
"""


class DetailFindMission(smach.State):
    def __init__(self, name, coarse_find_func, detail_find_func):
        rospy.init_node(name)

        self.sm = smach.StateMachine(outcomes=['mission successful',
                                               'mission aborted'])
        self.debug_pub = rospy.Publisher('/debug_image', Image, queue_size=1)
        with self.sm:
            smach.StateMachine.add('CoarseFind',
                                   CoarseFind(self.debug_pub, coarse_find_func),
                                   transitions={'succeeded': 'DetailFind',
                                                'aborted': 'mission aborted'})
            smach.StateMachine.add('DetailFind',
                                   DetailFind(self.debug_pub, detail_find_func),
                                   transitions={'failed': 'CoarseFind',
                                                'succeeded': 'mission successful',
                                                'aborted': 'mission aborted'})
        self.sis = smach_ros.IntrospectionServer(name, self.sm, '/SM_ROOT')
        self.sis.start()
        rospy.loginfo('Initialized {0} node.'.format(name))

    def execute(self):
        rospy.loginfo('Executing mission.')
        self.sm.execute()
        self.sis.stop()