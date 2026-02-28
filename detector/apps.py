from django.apps import AppConfig


class DetectorConfig(AppConfig):
    name = "detector"

    def ready(self):
        """
        Load PaliGemma model when Django starts
        This ensures the model is ready before any requests come in
        """
        print("=" * 60)
        print("🔄 Loading PaliGemma model on startup...")
        print("=" * 60)

        try:
            from .inference_utils import load_model
            model, processor = load_model()
            print(f"✅ Model loaded successfully on {model.device}")
            print("=" * 60)
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            print("=" * 60)
            import traceback
            traceback.print_exc()
