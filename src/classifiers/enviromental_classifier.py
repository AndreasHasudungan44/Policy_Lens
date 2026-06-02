from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import pandas as pd
import logging
from datetime import datetime


def setup_logger(log_file="environmental_classifier.log"):
    logger = logging.getLogger("environmental_classifier")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()


def load_environment_classifier():
    tokenizer_name = "ESGBERT/EnvironmentalBERT-environmental"
    model_name = "ESGBERT/EnvironmentalBERT-environmental"

    logger.info(f"Loading model: {model_name}")

    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_name,
        model_max_length=512,
    )

    pipe_env = pipeline(
        "text-classification",
        model=model,
        tokenizer=tokenizer,
        # device=0,
    )

    logger.info("Pipeline initialized successfully")
    return pipe_env

# -----------------------------------------------------------------------------
# Load data
# -----------------------------------------------------------------------------
data_path = "data/silver/chunks.parquet"

logger.info(f"Loading parquet file: {data_path}")

df = pd.read_parquet(data_path)

logger.info(f"Loaded dataframe with {len(df)} rows")

# -----------------------------------------------------------------------------
# Run predictions
# -----------------------------------------------------------------------------
pipe_env = load_environment_classifier()

logger.info("Starting predictions...")
start_time = datetime.now()

predictions = pipe_env(
    df["text"].dropna().astype(str).tolist(),
    padding=True,
    truncation=True,
    batch_size=16,
)

elapsed = datetime.now() - start_time
logger.info(f"Predictions completed in {elapsed}")

# -----------------------------------------------------------------------------
# Save predictions
# -----------------------------------------------------------------------------
df_classed = df.dropna(subset=["text"]).copy()

df_classed["label"] = [pred["label"] for pred in predictions]
df_classed["score"] = [pred["score"] for pred in predictions]

logger.info("Prediction columns added to dataframe")

output_path = "data/gold/chunks_classified.parquet"
df_classed.to_parquet(output_path, index=False)

logger.info(f"Saved classified dataframe to: {output_path}")

label_counts = df_classed["label"].value_counts().to_dict()
logger.info(f"Label distribution: {label_counts}")

print(df_classed[["label", "score", "text"]].head())