import pyautogui
import subprocess
import time


class DesktopController:

    def move_mouse(self, x, y, duration=0.5):
        pyautogui.moveTo(int(x), int(y), duration=duration)

    def click(self):
        time.sleep(0.15)
        pyautogui.click(button="left")
        time.sleep(0.15)

    def double_click(self):
        time.sleep(0.15)
        pyautogui.doubleClick(button="left")
        time.sleep(0.15)

    def right_click(self):
        time.sleep(0.15)
        pyautogui.rightClick()
        time.sleep(0.15)

    def write(self, text):
        pyautogui.write(text, interval=0.03)

    def press(self, key):
        pyautogui.press(key)

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)

    def open_program(self, program):
        subprocess.Popen(program)

    def wait(self, seconds):
        time.sleep(seconds)