#!/usr/bin/env python2

'''
Find the target from contour detection and the contours nesting.

Usage:
    ./polarity_find.py <image>
'''

import cv2
import numpy as np


class PolarityFind:
    def __init__(self, center_black, number_of_rings, debug=True):
        self._center_black = center_black
        self._number_of_rings = number_of_rings
        self._debug = debug

    def find_contours(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # TODO: Should we add more blur? Looked like polarity find worked
        # better with unfocused pictures.
        image = cv2.medianBlur(image, 13)
        # TODO: Fix the threshold. It worked better for us with 100, but we need to test.
        #_, threshold = cv2.threshold(image, 180, 1, cv2.THRESH_BINARY)
        _, threshold = cv2.threshold(image, 100, 1, cv2.THRESH_BINARY)

        if threshold is None or threshold.size == 0:
            return None, None

        # FIXME: the outer rectangle of the ROI is detected as contour.. what do do about that?
        contours, hierarchy = cv2.findContours(threshold, cv2.RETR_TREE,
                                               cv2.CHAIN_APPROX_SIMPLE)

        if hierarchy is not None:
            hierarchy = hierarchy[0]

        return contours, hierarchy

    def find_target(self, image):
        '''
        Return the center of the target in pixel coordinates as tuple (x, y).
        '''
        self.resize = 500
        #ratio = 1.0*self.resize/max(image.shape[:2])
        #if ratio < 1:
        #    image = cv2.resize(image, (0,0), fx=ratio, fy=ratio)
 
        contours, hierarchy = self.find_contours(image)
        if contours is None or hierarchy is None:
            return (None, None)

        contours_idx = [i for i, c in enumerate(contours) if len(c) >= 40]

        # Find leaf contours with parent and at least 50 points.
        # TODO: This doesn't work correctly. Too many false negatives..
        # Also, looks like this isn't a terrible performance issue to go over
        # all the contours.
        leaf_contours_idx = [i for i in contours_idx if len(contours[i]) >= 4 and
                             hierarchy[i][2] >= 0 and hierarchy[i][3] < 0]

        # DEBUG OUTPUT
        if self._debug:
            # TODO/FIXME:
            # this draws the contours on image, which is a partial view of the
            # original image. Perhaps this doesn't work correclty? or maybe it's
            # too slow?
            cv2.drawContours(image, contours, -1, (0, 0, 255), 5)
            cv2.drawContours(image, [contours[i] for i in leaf_contours_idx], -1, (0, 255, 0), 4)
            cv2.drawContours(image, [contours[i] for i in contours_idx], -1, (255, 0, 0), 3)

        # Go up and check polarity
        # FIXME: Until leaf_contours_idx is fixed, go over all the contours.
        #for i in leaf_contours_idx:
        for i in range(len(contours)):
            polarity = self._center_black
            inner_counter = 0
            idx = i
            while idx >= 0:
                area = cv2.contourArea(contours[idx], True)

                if area > 0 and polarity or area < 0 and not polarity:
                    inner_counter += 1
                    polarity = not polarity
                #else:
                #    # Go to next in same hierarchy level
                #    idx = hierarchy[idx][0]
                #    continue

                if inner_counter > 3:
                    # TODO/FIXME: This returns the diameter of the inner white circle!
                    # TODO: check all circles (parents)
                    moments = cv2.moments(contours[idx])
                    x = int(moments['m10']/moments['m00'])
                    y = int(moments['m01']/moments['m00'])
                    r = np.sqrt(4*cv2.contourArea(contours[idx])/np.pi)
                    r = 5./2 * r # circle / inner white circle radius ratio
                    return ((x, y), r)
                    #return ((x/ratio, y/ratio), np.sqrt(4*cv2.contourArea(contours[idx])/ratio**2/np.pi))
                idx = hierarchy[idx][2]

        return (None, None)

if __name__ == '__main__':
    import sys
    image = cv2.imread(sys.argv[1])

    center, size = PolarityFind(True, 3).find_target(image)
    print 'center:', center
    if center is not None:
        cv2.circle(image, center, 5, (0, 0, 255), 5)
        cv2.imshow('model', image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print 'could not find target'
        
