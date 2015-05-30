import numpy as np
import cv2

import rospy
import tf

from . import MissionState
from qtcopter.navigation.Camera import default_camera
from .utils import rect_contour

class CoarseFind(MissionState):
    def __init__(self, delta_pub, debug_pub, find_roi_func, camera=default_camera):
        MissionState.__init__(self,
                              delta_pub,
                              debug_pub,
                              outcomes=['succeeded',
                                        'aborted'],
                              output_keys=['rois'])
        if find_roi_func is None:
            rospy.logwarn('CoarseFind: Using dummy ROI finder function.')
            self._find_roi = lambda image, **kw: [rect_contour((0, 0, image.shape[1], image.shape[0]))]
        else:
            self._find_roi = find_roi_func
        self._camera = camera
        self._pub = tf.TransformBroadcaster()

    def publish_offset(self, height, rois):
        # for balldrop, move towards target
        # otherwise, just continue with detailed find
        if not rospy.get_param('camera/pointing_downwards') or height<2:
            return 'succeeded'

        # choose first ROI (should be sorted)
        roi = rois[0]
        image_width = rospy.get_param('camera/image_width')
        image_height = rospy.get_param('camera/image_height')

        # TODO: find ROI center. Currently simply center of bounding rectangle,
        # but we can use center of mass
        rect = cv2.boundingRect(roi)
        center = (rect[0]+rect[2]/2.0, rect[1]+rect[3]/2.0)

        # Get offset in pixels
        offset_px = (center[0]-image_width/2.0, center[1]-image_height/2.0)

        # Get distance in millimetres
        offset = self._camera.get_ground_offset(offset_px, height)

        # if target near edge, move to edge
        is_edge_close = lambda value, size: 1.0*value/size<0.1 or 1.0*(size-value)/size<0.1
        close_left  = is_edge_close(rect[0], image_width)
        close_top   = is_edge_close(rect[1], image_height)
        close_right = is_edge_close(rect[0]+rect[2], image_width)
        close_bot   = is_edge_close(rect[1]+rect[3], image_height)

        # if ROI is not close to edge..
        if not (close_left or close_top or close_right or close_bot):
            return 'succeeded'

        # if center of mass is nearby, don't move
        if abs(offset_px[0]/image_width) < 0.2 and abs(offset_px[1]/image_height) < 0.2:
            return 'succeeded'

        if rospy.get_param('camera/pointing_downwards'):
            # Camera points to the ground
            # -> distance to object is z coordinate
            x, y = offset
            z = 0
            camera_frame = 'downward_cam_optical_frame'
        else:
            # Camera is facing forward
            # -> distance to object is y coordinate
            x, z = offset
            y = 0
            camera_frame = 'cam_optical_frame'

        # finally, fly to center of mass
        self.publish_delta(camera_frame, (x, y, z), 0)

        # continue with coarse find until we are above ROI
        return None

    def on_execute(self, userdata, image, height):
        '''
        Runs the "coarse find" algorithm and returns a region of interest.
        '''
        rospy.loginfo('Trying to find coarse ROI in image, height = ' + str(height))
        rois = self._find_roi(image, height=height, camera=self._camera)

        def draw_roi():
            rospy.logdebug('Publishing coarse ROI.')
            cv2.drawContours(image, rois, -1, (0, 0, 255), 3)
            for i, cont in enumerate(rois):
                rect = cv2.boundingRect(cont)
                cv2.rectangle(image, rect[0:2], (rect[0]+rect[2], rect[1]+rect[3]), (0, 255, 255), 3)
            return image

        if rois is None or len(rois)==0:
            return None

        self.publish_debug_image(draw_roi)

        userdata.rois = rois
        return self.publish_offset(height, rois)
