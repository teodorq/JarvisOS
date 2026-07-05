import pyautogui
import subprocess
import time


class DesktopController:

    def move_mouse(self, x, y, duration=0.5):
        pyautogui.moveTo(x, y, duration=duration)

    def click(self):
        pyautogui.click()

    def double_click(self):
        pyautogui.doubleClick()

    def right_click(self):
        pyautogui.rightClick()

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