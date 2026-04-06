"""
PilotSuite Styx - Advanced ML Module

Deep Learning, Federated Learning, Online Learning, Model Registry, and Inference Engine.
"""
from .deep_learning import LSTMModel, TransformerModel, DeepLearningPipeline
from .federated_learning import FederatedLearningCoordinator, FLClient, SecureAggregator
from .online_learning import OnlineLearner, ContinuousModelUpdater, StreamingDataProcessor
from .model_registry import ModelRegistry, ModelVersion, ModelMetadata
from .inference_engine import InferenceEngine, RealTimePredictor, BatchPredictor

__version__ = "1.0.0"
__all__ = [
    "LSTMModel",
    "TransformerModel",
    "DeepLearningPipeline",
    "FederatedLearningCoordinator",
    "FLClient",
    "SecureAggregator",
    "OnlineLearner",
    "ContinuousModelUpdater",
    "StreamingDataProcessor",
    "ModelRegistry",
    "ModelVersion",
    "ModelMetadata",
    "InferenceEngine",
    "RealTimePredictor",
    "BatchPredictor",
]
