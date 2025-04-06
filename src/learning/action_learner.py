import pyautogui
import keyboard
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Any


class ActionLearner:
    def __init__(self):
        self.actions_file = "data/learned_actions.json"
        self.actions: Dict[str, List[Dict[str, Any]]] = self.load_actions()
        self.is_recording = False
        self.current_action = []
        self.last_mouse_pos = None
        self.last_click_time = 0

    def load_actions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Cargar acciones aprendidas desde el archivo."""
        if os.path.exists(self.actions_file):
            with open(self.actions_file, "r") as f:
                return json.load(f)
        return {}

    def save_actions(self):
        """Guardar acciones aprendidas en el archivo."""
        os.makedirs("data", exist_ok=True)
        with open(self.actions_file, "w") as f:
            json.dump(self.actions, f, indent=4)

    def start_recording(self):
        """Iniciar grabación de acciones."""
        self.is_recording = True
        self.current_action = []
        self.last_mouse_pos = pyautogui.position()
        self.last_click_time = time.time()

    def stop_recording(self):
        """Detener grabación de acciones."""
        self.is_recording = False
        if self.current_action:
            action_name = f"action_{len(self.actions) + 1}"
            self.actions[action_name] = self.current_action
            self.save_actions()

    def record_mouse_movement(self):
        """Grabar movimiento del mouse."""
        if not self.is_recording:
            return

        current_pos = pyautogui.position()
        if current_pos != self.last_mouse_pos:
            self.current_action.append(
                {
                    "type": "mouse_move",
                    "x": current_pos[0],
                    "y": current_pos[1],
                    "timestamp": time.time(),
                }
            )
            self.last_mouse_pos = current_pos

    def record_click(self, button: str, pressed: bool):
        """Grabar clic del mouse."""
        if not self.is_recording:
            return

        current_time = time.time()
        if current_time - self.last_click_time > 0.1:  # Evitar dobles clics
            self.current_action.append(
                {
                    "type": "mouse_click",
                    "button": button,
                    "pressed": pressed,
                    "x": pyautogui.position()[0],
                    "y": pyautogui.position()[1],
                    "timestamp": current_time,
                }
            )
            self.last_click_time = current_time

    def record_keyboard(self, event):
        """Grabar pulsación de tecla."""
        if not self.is_recording:
            return

        self.current_action.append(
            {
                "type": "keyboard",
                "key": event.name,
                "pressed": event.event_type == "down",
                "timestamp": time.time(),
            }
        )

    def replay_action(self, action_name: str):
        """Reproducir una acción grabada."""
        if action_name not in self.actions:
            return False

        for step in self.actions[action_name]:
            if step["type"] == "mouse_move":
                pyautogui.moveTo(step["x"], step["y"])
            elif step["type"] == "mouse_click":
                if step["pressed"]:
                    pyautogui.mouseDown(button=step["button"])
                else:
                    pyautogui.mouseUp(button=step["button"])
            elif step["type"] == "keyboard":
                if step["pressed"]:
                    keyboard.press(step["key"])
                else:
                    keyboard.release(step["key"])

            time.sleep(0.01)  # Pequeña pausa entre acciones

        return True

    def learn_from_pattern(self, action_name: str, pattern: List[Dict[str, Any]]):
        """Aprender un nuevo patrón de acciones."""
        self.actions[action_name] = pattern
        self.save_actions()

    def get_similar_actions(self, current_action: List[Dict[str, Any]]) -> List[str]:
        """Encontrar acciones similares a la actual."""
        similar_actions = []

        for action_name, action_pattern in self.actions.items():
            if self._compare_actions(current_action, action_pattern):
                similar_actions.append(action_name)

        return similar_actions

    def _compare_actions(
        self, action1: List[Dict[str, Any]], action2: List[Dict[str, Any]]
    ) -> bool:
        """Comparar dos secuencias de acciones."""
        if len(action1) != len(action2):
            return False

        for step1, step2 in zip(action1, action2):
            if step1["type"] != step2["type"]:
                return False

            if step1["type"] == "mouse_move":
                if (
                    abs(step1["x"] - step2["x"]) > 10
                    or abs(step1["y"] - step2["y"]) > 10
                ):
                    return False

        return True
