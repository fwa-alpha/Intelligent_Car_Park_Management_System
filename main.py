import os

import time

import random

from datetime import datetime



if not os.environ.get("DISPLAY"):

    os.environ["DISPLAY"] = ":0"



auth_cookie = "no39/unix:0 MIT-MAGIC-COOKIE-1 fab28472a152258e19d8b2e2ca1ed074。"

os.system(f"xauth add {auth_cookie}")

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import pytesseract
import numpy as np
import re
from collections import Counter

SIMULATE_HARDWARE = False

GPIO_FRONT_MOTOR = 14    # 前门电机
GPIO_FRONT_IR = 6       # 前门红外
GPIO_REAR_IR = 19        # 后面红外
GPIO_REAR_MOTOR = 13     # 后门电机
GPIO_RED_LIGHT = 21      # 控制红灯
GPIO_YELLOW_LIGHT = 20   # 控制黄灯

if not SIMULATE_HARDWARE:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)

    GPIO.setup(GPIO_FRONT_MOTOR, GPIO.OUT)
    GPIO.setup(GPIO_REAR_MOTOR, GPIO.OUT)
    GPIO.setup(GPIO_RED_LIGHT, GPIO.OUT)
    GPIO.setup(GPIO_YELLOW_LIGHT, GPIO.OUT)

    GPIO.setup(GPIO_FRONT_IR, GPIO.IN)
    GPIO.setup(GPIO_REAR_IR, GPIO.IN)
    current_state = GPIO.input(GPIO_FRONT_IR)
    print(f"IR Pin Status: {current_state}")

pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'


class ParkingSystemApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Intelligent Parking Management System")
        self.root.geometry("850x550")
        self.root.configure(bg="#f0f0f0")

        self.rate_per_minute = 0.1
        self.max_spaces = 5
        self.parked_cars_data = {}

        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=3)
        self.root.columnconfigure(0, weight=5)
        self.root.columnconfigure(1, weight=2)

        self.create_widgets()

        self.set_gpio_light(red_on=False, yellow_on=False)
        self.front_ir_active = False

        self.root.rowconfigure(0, weight=1)

        self.front_pwm = GPIO.PWM(GPIO_FRONT_MOTOR, 50)
        self.front_pwm.start(0)

        self.rear_pwm = GPIO.PWM(GPIO_REAR_MOTOR, 50)
        self.rear_pwm.start(0)
        self.is_scanning=False

    def run_ocr_logic(self, cam_idx):
        cap = cv2.VideoCapture(cam_idx)
        if not cap.isOpened():
            messagebox.showerror("Error", f"无法打开摄像头 {cam_idx}！")
            return None

        results_list = []
        try:
            for i in range(11):
                for _ in range(4): cap.read()
                ret, frame = cap.read()
                if not ret: continue

                h, w = frame.shape[:2]
                roi = frame[int(h * 0.25):int(h * 0.75), int(w * 0.1):int(w * 0.9)]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
                thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                               cv2.THRESH_BINARY, 11, 8)
                processed_img = cv2.copyMakeBorder(thresh, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)

                raw_text = pytesseract.image_to_string(processed_img, lang='eng', config='--psm 6')
                clean_s = "".join([c for c in raw_text.upper() if c.isalnum()])

                match = re.search(r'([A-Z]{1,5}).*?([A-Z0-9])([0-9]{5})', clean_s)
                if match:
                    prefix, city, nums = match.group(1), match.group(2), match.group(3)
                    if any(x in prefix for x in ['OW', 'WU', 'CW', 'HU']): prefix = "HUA"
                    if city in ['O', 'V', 'L', '0']: city = 'E'
                    results_list.append(f"{prefix} {city} {nums}")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            cv2.waitKey(100)

        if not results_list: return None
        return Counter(results_list).most_common(1)[0][0]


    def simulate_car_entry(self):
        if len(self.parked_cars_data) >= self.max_spaces:
            self.set_gpio_light(red_on=True, yellow_on=False)
            messagebox.showerror("Warning", "No spaces available!")
            return

        plate = self.run_ocr_logic(0)
        if not plate:
            messagebox.showwarning("Retry", "Recognition failed, please adjust position.")
            return

        if plate in self.parked_cars_data:
            messagebox.showinfo("Wait", f"Car {plate} is already inside.")
            return


        self.parked_cars_data[plate] = [time.time(), None]

        self.refresh_table()
        self.update_count_display()
        self.set_gpio_light(False, False)

        self.control_motor(GPIO_FRONT_MOTOR, duration=5000)

        #messagebox.showinfo("Entry success", f"License: {plate}\nWelcome to the lot!")

    def open_gate_calculate(self):
        if not self.parked_cars_data:
            messagebox.showwarning("提示", "场内目前没有车辆！")
            return

        # 1. 运行出口摄像头识别 (Camera 2)
        plate = self.run_ocr_logic(2)
        if not plate:
            return

        if plate not in self.parked_cars_data:
            messagebox.showerror("识别错误", f"车辆 【{plate}】 不在场内记录中！")
            return

        in_time, pay_time = self.parked_cars_data[plate]

        # 2. 检查缴费状态
        if pay_time is None:
            self.set_gpio_light(red_on=False, yellow_on=True)  # 亮黄灯提示收费
            duration, fee = self.calculate_time_and_fee(in_time, None)

            is_paid = messagebox.askyesno(
                "缴费确认",
                f"车牌号: {plate}\n入场时长: {duration} 分钟\n应付金额: {fee:.1f} 元\n\n是否已收到现金/扫码支付？"
            )

            if is_paid:
                self.parked_cars_data[plate][1] = time.time()  # 记录缴费时间
                self.set_gpio_light(False, False)
                self.refresh_table()
                messagebox.showinfo("支付成功", f"车辆 {plate} 支付成功！\n请准备离场。")

            else:
                messagebox.showwarning("支付取消", "未完成支付，闸机无法开启。")
                return

        # 3. 检查缴费是否超时
        time_since_pay = time.time() - pay_time
        if time_since_pay > 180:
            self.set_gpio_light(red_on=False, yellow_on=True)
            self.parked_cars_data[plate][1] = None  # 重置为未缴费
            self.refresh_table()
            messagebox.showwarning("超时提示", f"车辆 {plate} 缴费已超时！\n请重新缴纳超时费用。")
            return

        # 4. 执行开门动作
        self.set_gpio_light(False, False)

        # 触发后门电机动作
        print("Motor should turn now")
        self.control_motor(GPIO_REAR_MOTOR, duration=5000)

        # 5. 清理数据并更新界面
        del self.parked_cars_data[plate]
        self.refresh_table()
        self.update_count_display()
        messagebox.showinfo("一路平安", f"车牌号: {plate}\n验证通过，闸机已开启！")

    def pay_current_car(self):

        if not self.parked_cars_data:
            messagebox.showinfo("Tip", "No cars currently in the lot.")
            return
        import tkinter.simpledialog as sd
        plate = sd.askstring("Simulate Pay", "Enter License Plate to pay:")

        if plate and plate in self.parked_cars_data:
            self.parked_cars_data[plate][1] = time.time()
            self.set_gpio_light(red_on=False, yellow_on=False)
            self.refresh_table()
            messagebox.showinfo("Success", f"Payment confirmed for {plate}!")
        else:
            if plate:
                messagebox.showerror("Error", f"Car {plate} not found!")
    def create_widgets(self):
        self.count_var = tk.StringVar()
        self.count_label = tk.Label(self.root, textvariable=self.count_var, font=("Times New Roman", 16, "bold"),
                                    bg="#ecf0f1", relief="ridge", bd=3)
        self.count_label.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.update_count_display()

        right_top_frame = tk.Frame(self.root, bg="#f0f0f0")
        right_top_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        tk.Label(right_top_frame, text="Station Console", font=("Times New Roman", 14, "bold"),
                 bg="#34495e", fg="white", padx=10, pady=5).pack(fill="x")
        self.entry_btn = tk.Button(right_top_frame, text="Camera 1: Scan Entry", font=("Times New Roman", 11, "bold"),
                                   bg="#3498db", fg="white", command=self.simulate_car_entry)
        self.entry_btn.pack(fill="x", pady=(10, 0))

        table_frame = tk.Frame(self.root)
        table_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        cols = ("license", "time", "fee", "status")
        self.car_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        self.car_tree.pack(side="left", fill="both", expand=True)
        for col, head in zip(cols, ["License Plate", "Park Time (min)", "Fee (￥)", "Pay Status"]):
            self.car_tree.heading(col, text=head)
            self.car_tree.column(col, anchor="center", width=120)
        scrollbar = tk.Scrollbar(table_frame, command=self.car_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.car_tree.config(yscrollcommand=scrollbar.set)

        right_bottom_frame = tk.Frame(self.root, bg="#f0f0f0")
        right_bottom_frame.grid(row=1, column=1, padx=20, pady=(0, 20), sticky="nsew")
        self.gate_btn = tk.Button(right_bottom_frame, text="CAMERA 2\nSCAN & EXIT",
                                  font=("Times New Roman", 14, "bold"),
                                  bg="#2ecc71", fg="white", bd=5, command=self.open_gate_calculate)
        self.gate_btn.pack(fill="both", expand=True, pady=(0, 10))
        self.pay_btn = tk.Button(right_bottom_frame, text="SIMULATE PAY", font=("Times New Roman", 12, "bold"),
                                 bg="#f39c12", fg="white", bd=3, command=self.pay_current_car)
        self.pay_btn.pack(fill="x")

    def set_gpio_light(self, red_on, yellow_on):
        """控制红黄灯"""
        if SIMULATE_HARDWARE:
            print(f"[HW] Red(Pin21):{'ON' if red_on else 'OFF'} | Yellow(Pin20):{'ON' if yellow_on else 'OFF'}")
        else:
            GPIO.output(GPIO_RED_LIGHT, GPIO.HIGH if red_on else GPIO.LOW)
            GPIO.output(GPIO_YELLOW_LIGHT, GPIO.HIGH if yellow_on else GPIO.LOW)

    def control_motor(self, pin, duration=5000):
        pwm_device = self.front_pwm if pin == GPIO_FRONT_MOTOR else self.rear_pwm

        pwm_device.ChangeDutyCycle(10.0)

        self.root.after(600, lambda: pwm_device.ChangeDutyCycle(0))

        self.root.after(duration, lambda: self.reset_servo(pwm_device))

    def reset_servo(self, pwm_device):

        pwm_device.ChangeDutyCycle(5.5)

        self.root.after(600, lambda: pwm_device.ChangeDutyCycle(0))

    def close_gate_servo(self, pwm_device):

        if not SIMULATE_HARDWARE:
            pwm_device.ChangeDutyCycle(2.5)  # 回到0度

            self.root.after(500, lambda: pwm_device.ChangeDutyCycle(0))

    def check_ir_sensors(self):

        if SIMULATE_HARDWARE:
            return False
        else:

            front_val = GPIO.input(GPIO_FRONT_IR)
            rear_val = GPIO.input(GPIO_REAR_IR)
            return front_val, rear_val

    def calculate_time_and_fee(self, start_time, pay_time):
        current = time.time() if pay_time is None else pay_time
        duration_s = current - start_time
        duration_m = max(1, int(duration_s / 60))
        return duration_m, duration_m * self.rate_per_minute

    def update_count_display(self):
        count = len(self.parked_cars_data)
        avail = self.max_spaces - count
        if avail <= 0:
            self.count_var.set("Information Board\n\nSpaces available: 0 (FULL)")
            self.count_label.config(bg="#e74c3c", fg="white")
        else:
            self.count_var.set(f"Information Board\n\nSpaces available: {avail}")
            self.count_label.config(bg="#ecf0f1", fg="black")

    def monitor_hardware(self):
        if not SIMULATE_HARDWARE:

            if getattr(self, 'is_scanning', False):
                self.root.after(200, self.monitor_hardware)
                return

            current_state = GPIO.input(GPIO_FRONT_IR)
            if current_state == GPIO.LOW:
                if not self.front_ir_active:
                    self.front_ir_active = True
                    print(">>> 检测到车辆，开始识别...")
                    self.is_scanning = True

                    self.root.after(100, self.auto_entry_process)
            else:
                self.front_ir_active = False

        self.root.after(100, self.monitor_hardware)

    def auto_entry_process(self):
        try:
            self.simulate_car_entry()
        finally:
            self.is_scanning = False
            print(">>> 识别流程结束，恢复监控")
    def refresh_table(self):
        for item in self.car_tree.get_children(): self.car_tree.delete(item)
        for car, data in self.parked_cars_data.items():
            duration, fee = self.calculate_time_and_fee(data[0], data[1])
            if data[1] is None:
                status = "Unpaid"
            else:
                rem = 180 - int(time.time() - data[1])
                status = f"Paid ({rem}s)" if rem > 0 else "Unpaid"
                if rem <= 0: self.parked_cars_data[car][1] = None
            self.car_tree.insert("", "end", values=(car, duration, f"{fee:.1f}", status))


if __name__ == "__main__":
    root = tk.Tk()
    app = ParkingSystemApp(root)

    def auto_refresh():
        app.refresh_table()
        root.after(1000, auto_refresh)


    app.monitor_hardware()
    auto_refresh()
    root.mainloop()