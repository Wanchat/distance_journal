from kivy.app import App
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.properties import ObjectProperty, StringProperty, NumericProperty
from kivy.lang.builder import Builder
from kivy.uix.popup import Popup
import cv2
import dlib
import numpy as np
from plyer import notification
from find_angle_distance import Find_angle_distance


Builder.load_file("gui/distanceKV.kv")
Window.size = (480, 800)


class Face_detect:
    model_hog = dlib.get_frontal_face_detector()
    model_haar = cv2.CascadeClassifier("res/model/haarcascade_frontalface_default.xml")
    f_txt = "res/model/opencv_face_detector.pbtxt"
    f_pb = "res/model/opencv_face_detector_uint8.pb"
    model_dnn = cv2.dnn.readNetFromTensorflow(f_pb, f_txt)
    predict_landmark = dlib.shape_predictor("res/model/shape_predictor_5_face_landmarks.dat")

    find_distance = Find_angle_distance()

    def get_frame(self, frame):
        self.frame = frame

    def haar(self, model):
        dets = model.detectMultiScale(self.frame, scaleFactor=1.3, minNeighbors=5)

        self.face_list = []
        for x, y, w, h in dets:
            left, top, right, bottom = x, y, x + w, y + h
            self.face_list.append([left, top, right, bottom])
        return self.face_list

    def hog_dlib(self, model):
        gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        dets = model(gray, 0)

        self.face_list = []
        for det in dets:
            self.face_list.append([det.left(), det.top(), det.right(), det.bottom()])
        return self.face_list

    def dnn(self, model):
        rows = self.frame.shape[0]
        cols = self.frame.shape[1]
        model.setInput(cv2.dnn.blobFromImage(self.frame, size=(300, 300), swapRB=True, crop=False))
        face_Out = model.forward()

        self.face_list = []
        for detection in face_Out[0, 0, :, :]:
            score = float(detection[2])

            if score < 0.6:
                continue
            box = detection[3:7] * np.array([cols, rows, cols, rows])
            (left, top, right, bottom) = box.astype("int")

            origin_w_h = bottom - top
            top = int(top + (origin_w_h) * 0.15)
            bottom = int(bottom - (origin_w_h) * 0.05)
            margin = ((bottom - top) - (right - left)) // 2
            left = left - margin if (bottom - top - right + left) % 2 == 0 else left - margin - 1
            right = right + margin
            self.face_list.append([left, top, right, bottom])
        return self.face_list

    def method_face(self, select_method):
        if select_method == "HAAR":
            self.face = self.haar(self.model_haar)

        elif select_method == "HOG":
            self.face = self.hog_dlib(self.model_hog)
        else:
            self.face = self.dnn(self.model_dnn)
        return self.face

    def face_landmark(self, face):
        if face:
            # l,t,r,b = face[-1][0:len(face)]
            for l,t,r,b in face:

                shape = self.predict_landmark(self.frame, dlib.rectangle(int(l),int(t),int(r),int(b)))

                extand_eye = lambda  near, far: (far - near) // 2 + near

                r_e_x = extand_eye(shape.part(2).x, shape.part(3).x)
                r_e_y = extand_eye(shape.part(2).y, shape.part(3).y) \
                    if shape.part(3).y > shape.part(2).y else extand_eye(shape.part(3).y, shape.part(2).y)

                l_e_x = extand_eye(shape.part(1).x, shape.part(0).x)
                l_e_y = extand_eye(shape.part(1).y, shape.part(0).y) \
                    if shape.part(0).y > shape.part(1).y else extand_eye(shape.part(0).y, shape.part(1).y)

                c_x = extand_eye(r_e_x, l_e_x)
                c_y = extand_eye(r_e_y, l_e_y)

                points = {"view_center":[c_x, c_y], "eye_right":[r_e_x, r_e_y], "eye_left":[l_e_x, l_e_y]}
                return points

    def draw_face(self, face, t):
        # for points_faces in range(len(face)):
        #     x,y,w,h = face[points_faces][0:4]
        font = cv2.FONT_HERSHEY_SIMPLEX
        t_inpurt = f'{t:.2f} cm'
        s_text = 0.8

        box = cv2.getTextSize(t_inpurt, font, s_text, 1)
        w_t = box[0][0]
        h_t = box[0][1]

        overlay = self.frame.copy()
        opicity = 0.7

        for x,y,w,h in face:
            cv2.rectangle(overlay,(x,y), (x+w_t+3, y+h_t+6), (0,0,0), -1 )
            cv2.addWeighted(overlay, opicity, self.frame, 1-opicity, 0, self.frame)

            cv2.putText(self.frame,t_inpurt,(x+3,y+h_t+3),font, s_text, (0,0,255), 1)
            cv2.rectangle(self.frame, (x,y), (w,h), (0,0,0), 1)

    def draw_landmark(self, eye):
        cv2.circle(self.frame,(eye[0],eye[1]), 2, (0,0,0), -1)

    def distance(self, view_center, eye_right):
        self.find_distance.get_eye(view_center)
        setcam = self.find_distance.set_camera()
        status_v = self.find_distance.change_point_start_vertical()
        angle_v = self.find_distance.estimate_angle_vertical()
        distance = self.find_distance.estimate_distance(eye_right[0])
        return {"distance": distance, "angle": [angle_v, status_v[0]]}


class Change(Image):
    def output_frame(self, im):
        self.cols = im.shape[0]
        self.rows = im.shape[1]
        self.buf1 = cv2.flip(im, 0)
        self.buf = self.buf1.tostring()
        image_texture = Texture.create(size=(self.rows, self.cols), colorfmt='bgr')
        image_texture.blit_buffer(self.buf, colorfmt='bgr', bufferfmt='ubyte')
        self.texture = image_texture


class Show_text(Widget):
    number_frame = NumericProperty(0)
    distanc_text = StringProperty("")
    risk_text = StringProperty("")


class Main(Widget):
    show_text = ObjectProperty(None)
    btn_detect = ObjectProperty(None)
    change = ObjectProperty(None)

    def __init__(self, capture, **kwargs):
        super(Main, self).__init__(**kwargs)
        self.capture = capture
        self.output = self.change
        self.face_detect = Face_detect()
        self.choose = "HAAR"
        self.risk_status_text = ""
        self.frame_num = 0

    def detect_toggle(self):
        click = self.btn_detect.state == "down"
        if click:
            self.btn_detect.text = "Detecting Blink..."
            self.x = 1
        else:
            self.btn_detect.text = "Start Detect"
            self.x = 0
            self.show_text.distanc_text = ""

    def choose_clicked(self, value): # choose method
        self.choose = value
    
    def risk_status(self, x):
        r = ""
        if x < 40:
            r = 0
        elif x < 76:
            r = 1
        else:
            r = 2
        return r

    def risk_show(self, x):
        if x == 0:
            self.risk_status_text = "You are too close to the screen!"
        elif x == 1:
            self.risk_status_text = "Good! View"
        else:
            self.risk_status_text = "You are too far from the screen"

        self.show_text.risk_text = self.risk_status_text

    def noti(self, status, distance):
        if self.frame_num % 60 == 0:
            if status == 0 or status == 2:
                notification.notify(
                    title= "Risk !",
                    message=f"You have distance {round(distance)} cm",
                    app_icon="gui/ico/logo_eyeguard.ico",
                    timeout=2)

    def working(self, start, choose, frame):
        self.face_detect.get_frame(frame)

        if start == 1:
            self.frame_num += 1

            face = self.face_detect.method_face(choose)
            eyes = self.face_detect.face_landmark(face)

            if eyes:
                self.face_detect.draw_landmark(eyes["view_center"])
                self.distance = self.face_detect.distance(eyes["view_center"], eyes["eye_right"])
                self.show_text.distanc_text = f"{self.distance['distance']:.2f} cm"

                risk_status = self.risk_status(self.distance['distance'])
                self.risk_show(risk_status)

                self.noti(risk_status, self.distance['distance'])
                self.face_detect.draw_face(face, self.distance['distance'])
        else:
            self.frame_num = 0
            self.show_text.risk_text = ""

    def update(self, dt):
        frame = self.capture.read()[1]  # <<< start frame app
        self.working(self.x, self.choose, frame)
        self.output.output_frame(frame)


class DistanceApp(App):
    def build(self):
        capture = cv2.VideoCapture(0)
        app = Main(capture)
        Clock.schedule_interval(app.update, 1 / 30)
        return app


if __name__ == '__main__':
    DistanceApp().run()