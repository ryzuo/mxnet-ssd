from __future__ import print_function
import mxnet as mx
import numpy as np
from timeit import default_timer as timer
from dataset.testdb import TestDB
from dataset.iterator import DetIter

class Detector(object):
    """
    SSD detector which hold a detection network and wraps detection API

    Parameters:
    ----------
    symbol : mx.Symbol
        detection network Symbol
    model_prefix : str
        name prefix of trained model
    epoch : int
        load epoch of trained model
    data_shape : int
        input data resize shape
    mean_pixels : tuple of float
        (mean_r, mean_g, mean_b)
    batch_size : int
        run detection with batch size
    ctx : mx.ctx
        device to use, if None, use mx.cpu() as default context
    """
    def __init__(self, symbol, model_prefix, epoch, data_shape, mean_pixels, \
                 batch_size=1, ctx=None, run_video=False):
        self.ctx = ctx
        if self.ctx is None:
            self.ctx = mx.cpu()
        self._run_video = run_video
        load_symbol, args, auxs = mx.model.load_checkpoint(model_prefix, epoch)
        if symbol is None:
            symbol = load_symbol
        self.mod = mx.mod.Module(symbol, label_names=None, context=ctx)
        self.data_shape = data_shape
        self.mod.bind(data_shapes=[('data', (batch_size, 3, data_shape, data_shape))])
        self.mod.set_params(args, auxs)
        self.data_shape = data_shape
        self.mean_pixels = mean_pixels
        self.__colors = [
            (255, 0, 0),
            (255, 128, 0),
            (255, 255, 0),
            (0, 255, 0),
            (0, 128, 255),
            (0, 255, 255),
            (0, 0, 255),
            (255, 0, 255)
        ]

    def detect(self, det_iter, show_timer=False):
        """
        detect all images in iterator

        Parameters:
        ----------
        det_iter : DetIter
            iterator for all testing images
        show_timer : Boolean
            whether to print out detection exec time

        Returns:
        ----------
        list of detection results
        """
        num_images = det_iter._size
        if not isinstance(det_iter, mx.io.PrefetchingIter):
            det_iter = mx.io.PrefetchingIter(det_iter)
        start = timer()
        detections = self.mod.predict(det_iter).asnumpy()
        time_elapsed = timer() - start
        if show_timer:
            print("Detection time for {} images: {:.4f} sec".format(
                num_images, time_elapsed))
        result = []
        for i in range(detections.shape[0]):
            det = detections[i, :, :]
            res = det[np.where(det[:, 0] >= 0)[0]]
            result.append(res)
        #print(type(det_iter))
        del det_iter
        return result

    def im_detect(self, im_list, root_dir=None, extension=None, show_timer=False):
        """
        wrapper for detecting multiple images

        Parameters:
        ----------
        im_list : list of str
            image path or list of image paths
        root_dir : str
            directory of input images, optional if image path already
            has full directory information
        extension : str
            image extension, eg. ".jpg", optional

        Returns:
        ----------
        list of detection results in format [det0, det1...], det is in
        format np.array([id, score, xmin, ymin, xmax, ymax]...)
        """
        test_db = TestDB(im_list, root_dir=root_dir, extension=extension)
        test_iter = DetIter(test_db, 1, self.data_shape, self.mean_pixels,
                            is_train=False)
        return self.detect(test_iter, show_timer)

    def vd_detect(self, frame, show_timer=False):
        test_iter = DetIter(None, 1, self.data_shape, frame=frame,
                            mean_pixels=self.mean_pixels, is_train=False)
        return self.detect(test_iter, show_timer)

    def visualize_detection(self, img, dets, classes=[], thresh=0.6):
        """
        visualize detections in one image

        Parameters:
        ----------
        img : numpy.array
            image, in bgr format
        dets : numpy.array
            ssd detections, numpy.array([[id, score, x1, y1, x2, y2]...])
            each row is one object
        classes : tuple or list of str
            class names
        thresh : float
            score threshold
        """
        import matplotlib.pyplot as plt
        import random
        print(type(img))
        plt.imshow(img)
        height = img.shape[0]
        width = img.shape[1]
        colors = dict()
        print(dets.shape[0])
        for i in range(dets.shape[0]):
            cls_id = int(dets[i, 0])
            if cls_id >= 0:
                score = dets[i, 1]
                if score > thresh:
                    if cls_id not in colors:
                        colors[cls_id] = (random.random(), random.random(), random.random())
                    xmin = int(dets[i, 2] * width)
                    ymin = int(dets[i, 3] * height)
                    xmax = int(dets[i, 4] * width)
                    ymax = int(dets[i, 5] * height)
                    rect = plt.Rectangle((xmin, ymin), xmax - xmin,
                                         ymax - ymin, fill=False,
                                         edgecolor=colors[cls_id],
                                         linewidth=3.5)
                    plt.gca().add_patch(rect)
                    class_name = str(cls_id)
                    if classes and len(classes) > cls_id:
                        class_name = classes[cls_id]
                    plt.gca().text(xmin, ymin - 2,
                                    '{:s} {:.3f}'.format(class_name, score),
                                    bbox=dict(facecolor=colors[cls_id], alpha=0.5),
                                    fontsize=12, color='white')
        plt.show()

    def visualize_vdetection(self, img, dets, classes=[], thresh=0.6):
        import cv2
        height = img.shape[0]
        width = img.shape[1]
        colors = dict()
        for i in range(dets.shape[0]):
            cls_id = int(dets[i, 0])
            if cls_id >= 0:
                score = dets[i, 1]
                if score > thresh:
                    if cls_id not in colors:
                        colors[cls_id] = self.__colors[cls_id%len(self.__colors)]
                    xmin = int(dets[i, 2] * width)
                    ymin = int(dets[i, 3] * height)
                    xmax = int(dets[i, 4] * width)
                    ymax = int(dets[i, 5] * height)
                    cv2.rectangle(img, (xmin, ymin), (xmax, ymax), colors[cls_id],3)
                    class_name = str(cls_id)
                    if classes and len(classes) > cls_id:
                        class_name = classes[cls_id]
                    text = '{:s} {:.3f}'.format(class_name, score)
                    cv2.putText(img, text, (xmin, ymin-4), cv2.FONT_HERSHEY_TRIPLEX, 0.5, colors[cls_id], 1)
        cv2.imshow('IMIO Surveillance', img)

    def detect_and_visualize(self, im_list, root_dir=None, extension=None,
                             classes=[], thresh=0.6, show_timer=False):
        """
        wrapper for im_detect and visualize_detection

        Parameters:
        ----------
        im_list : list of str or str
            image path or list of image paths
        root_dir : str or None
            directory of input images, optional if image path already
            has full directory information
        extension : str or None
            image extension, eg. ".jpg", optional

        Returns:
        ----------

        """
        import cv2
        if self._run_video:
            cap = cv2.VideoCapture(0)
            while True:
                ret, frame = cap.read()
                img_file = './tmp/temp.jpg'
                im_list = []
                im_list.append(img_file)
                cv2.imwrite(img_file, frame)
                dets = self.im_detect(im_list, root_dir, extension, show_timer=show_timer)
                if not isinstance(im_list, list):
                    im_list = [im_list]
                assert len(dets) == len(im_list)
                for k, det in enumerate(dets):
                    self.visualize_vdetection(frame, det, classes, thresh)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        else:
            dets = self.im_detect(im_list, root_dir, extension, show_timer=show_timer)
            if not isinstance(im_list, list):
                im_list = [im_list]
            assert len(dets) == len(im_list)
            for k, det in enumerate(dets):
                img = cv2.imread(im_list[k])
                img[:, :, (0, 1, 2)] = img[:, :, (2, 1, 0)]
                self.visualize_detection(img, det, classes, thresh)
