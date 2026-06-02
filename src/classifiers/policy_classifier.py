from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import pandas as pd
import logging
from datetime import datetime

# -----------------------------------------------------------------------------
# Logger setup
# -----------------------------------------------------------------------------
def setup_logger(log_file="policy_classifier.log"):
    logger = logging.getLogger("policy_classifier")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if rerun in notebook
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()

# -----------------------------------------------------------------------------

# Load model and tokenizer

# -----------------------------------------------------------------------------

model_name = "industrialpolicygroup/industrialpolicy-classifier"

logger.info(f"Loading model: {model_name}")

tokenizer = AutoTokenizer.from_pretrained(model_name)

model = AutoModelForSequenceClassification.from_pretrained(model_name)

pipe = pipeline(

    task="text-classification",

    model=model,

    tokenizer=tokenizer,

    truncation=True,

    max_length=512,

    device=0 if torch.cuda.is_available() else -1,

)

logger.info("Pipeline initialized successfully")

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
logger.info("Starting predictions...")
start_time = datetime.now()

predictions = pipe(
    df["text"].tolist(),
    padding=True,
    truncation=True,
    batch_size=16
)

elapsed = datetime.now() - start_time

logger.info(f"Predictions completed in {elapsed}")

# -----------------------------------------------------------------------------
# Save predictions
# -----------------------------------------------------------------------------
df_classed = df.copy()

df_classed["label"] = [pred["label"] for pred in predictions]
df_classed["score"] = [pred["score"] for pred in predictions]

logger.info("Prediction columns added to dataframe")

# Optional: save output
output_path = "data/gold/chunks_classified.parquet"

df_classed.to_parquet(output_path, index=False)

logger.info(f"Saved classified dataframe to: {output_path}")

# -----------------------------------------------------------------------------
# Summary logs
# -----------------------------------------------------------------------------
label_counts = df_classed["label"].value_counts().to_dict()

logger.info(f"Label distribution: {label_counts}")

print(df_classed["label","score","text"].head())

# -----------------------------------------------------------------------------
# Example single prediction
# -----------------------------------------------------------------------------
#example_text = (
#    "Scope 1 emissions are reported here on a like-for-like basis "
#    "against the 2013 baseline and exclude emissions from additional "
#    "vehicles used during repairs."
#)
#
#example_prediction = pipe(
#    example_text,
#    padding=True,
#    truncation=True
#)
#
#logger.info(f"Example prediction: {example_prediction}")

#print(example_prediction)