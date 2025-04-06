import json
import os
from typing import Dict, List, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from ..utils.logger import get_logger

class AdaptiveLearning:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.vectorizer = TfidfVectorizer()
        self.classifier = MultinomialNB()
        self.learning_data = self._load_learning_data()
        self._train_model()
        
    def _load_learning_data(self) -> Dict[str, List[str]]:
        """Cargar datos de aprendizaje desde el archivo."""
        data_path = os.path.join('data', 'learning_data.json')
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.info("Creando nuevo archivo de datos de aprendizaje")
            return {
                "email": [],
                "whatsapp": [],
                "tms": [],
                "unknown": []
            }
    
    def _save_learning_data(self):
        """Guardar datos de aprendizaje en el archivo."""
        os.makedirs('data', exist_ok=True)
        data_path = os.path.join('data', 'learning_data.json')
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(self.learning_data, f, indent=4, ensure_ascii=False)
    
    def _train_model(self):
        """Entrenar el modelo de clasificación."""
        if not any(self.learning_data.values()):
            return
            
        # Preparar datos de entrenamiento
        texts = []
        labels = []
        
        for task_type, examples in self.learning_data.items():
            if task_type != "unknown":
                texts.extend(examples)
                labels.extend([task_type] * len(examples))
        
        if texts and labels:
            # Vectorizar textos
            X = self.vectorizer.fit_transform(texts)
            
            # Entrenar clasificador
            self.classifier.fit(X, labels)
    
    def analyze_command(self, command: str) -> str:
        """Analizar el comando y determinar el tipo de tarea."""
        if not any(self.learning_data.values()):
            return "unknown"
            
        # Vectorizar el comando
        try:
            X = self.vectorizer.transform([command])
            prediction = self.classifier.predict(X)[0]
            return prediction
        except:
            return "unknown"
    
    def learn_from_interaction(self, command: str, feedback: str = None):
        """Aprender de la interacción con el usuario."""
        # Si se proporciona feedback, actualizar la categorización
        if feedback and feedback in self.learning_data:
            self.learning_data[feedback].append(command)
            self._save_learning_data()
            self._train_model()
    
    def add_example(self, command: str, task_type: str):
        """Agregar un nuevo ejemplo de aprendizaje."""
        if task_type in self.learning_data:
            self.learning_data[task_type].append(command)
            self._save_learning_data()
            self._train_model()
    
    def get_statistics(self) -> Dict[str, int]:
        """Obtener estadísticas de aprendizaje."""
        return {
            task_type: len(examples)
            for task_type, examples in self.learning_data.items()
        } 