"""
Fine-tuning RoBERTa para fake news en español — Google Colab
=============================================================
Runtime → Change runtime type → T4 GPU

Usa el modelo BASE PlanTL-GOB-ES/roberta-large-bne (sin fine-tuning previo)
para evitar overfitting sobre el corpus FakeDeS.

Sube el resultado a analuciahm/tucuy-fake-news-spanish en HF.
"""

# CELDA 1
# !pip install transformers datasets evaluate scikit-learn accelerate huggingface_hub -q

# CELDA 2 — Login (reemplaza con tu token)
from huggingface_hub import login
login("TU_TOKEN_HF_AQUI")

# CELDA 3 — Cargar dataset FakeDeS
import pandas as pd

base = "https://github.com/jpposadas/FakeNewsCorpusSpanish/raw/refs/heads/master/"
df_train = pd.read_excel(base + "train.xlsx")
df_test  = pd.read_excel(base + "development.xlsx")

df_train["label"] = (df_train["Category"] == "Fake").astype(int)
df_test["label"]  = (df_test["Category"]  == "Fake").astype(int)
df_train["input_text"] = df_train["Headline"].fillna("") + " [SEP] " + df_train["Text"].fillna("")
df_test["input_text"]  = df_test["Headline"].fillna("")  + " [SEP] " + df_test["Text"].fillna("")
print("Train:", df_train.shape, "| Labels:", df_train["label"].value_counts().to_dict())

# CELDA 4 — Tokenizar
# IMPORTANTE: modelo BASE sin fine-tuning previo
MODEL_BASE = "PlanTL-GOB-ES/roberta-large-bne"

from transformers import AutoTokenizer
from datasets import Dataset

tokenizer = AutoTokenizer.from_pretrained(MODEL_BASE)
train_ds  = Dataset.from_dict({"text": df_train["input_text"].tolist(), "label": df_train["label"].tolist()})
test_ds   = Dataset.from_dict({"text": df_test["input_text"].tolist(),  "label": df_test["label"].tolist()})

def tokenize(batch):
    return tokenizer(batch["text"], truncation=True, max_length=512, padding="max_length")

train_ds = train_ds.map(tokenize, batched=True)
test_ds  = test_ds.map(tokenize, batched=True)
train_ds.set_format("torch", columns=["input_ids", "attention_mask", "label"])
test_ds.set_format("torch",  columns=["input_ids", "attention_mask", "label"])
print("Tokenizado OK")

# CELDA 5 — Fine-tuning
from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer
import evaluate, numpy as np

model = AutoModelForSequenceClassification.from_pretrained(MODEL_BASE, num_labels=2)
accuracy_metric = evaluate.load("accuracy")
f1_metric = evaluate.load("f1")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    acc = accuracy_metric.compute(predictions=predictions, references=labels)
    f1  = f1_metric.compute(predictions=predictions, references=labels, average="weighted")
    return {"accuracy": acc["accuracy"], "f1": f1["f1"]}

training_args = TrainingArguments(
    output_dir="./tucuy-finetuned",
    num_train_epochs=5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    warmup_steps=50,
    weight_decay=0.01,
    learning_rate=2e-5,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="accuracy",
    logging_steps=20,
    fp16=True,
    report_to="none",
)

trainer = Trainer(
    model=model, args=training_args,
    train_dataset=train_ds, eval_dataset=test_ds,
    compute_metrics=compute_metrics,
)
trainer.train()

# CELDA 6 — Evaluar y subir
results = trainer.evaluate()
print(f"Accuracy: {results['eval_accuracy']*100:.2f}%")
print(f"F1:       {results['eval_f1']*100:.2f}%")

if results["eval_accuracy"] >= 0.80:
    trainer.model.push_to_hub("analuciahm/tucuy-fake-news-spanish")
    tokenizer.push_to_hub("analuciahm/tucuy-fake-news-spanish")
    print("Modelo subido!")

# CELDA 7 — Convertir a ONNX cuantizado (~120MB para Render)
# !pip install "optimum[onnxruntime]" -q

from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from huggingface_hub import HfApi
import os

ort_model = ORTModelForSequenceClassification.from_pretrained(
    "analuciahm/tucuy-fake-news-spanish", export=True
)
quantizer = ORTQuantizer.from_pretrained(ort_model)
qconfig   = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)
quantizer.quantize(save_dir="./tucuy-onnx-quantized", quantization_config=qconfig)

size = sum(os.path.getsize(f"./tucuy-onnx-quantized/{f}") for f in os.listdir("./tucuy-onnx-quantized") if os.path.isfile(f"./tucuy-onnx-quantized/{f}")) / 1024**2
print(f"Tamaño ONNX: {size:.1f} MB")

tokenizer.save_pretrained("./tucuy-onnx-quantized")
api = HfApi()
api.create_repo(repo_id="analuciahm/tucuy-fake-news-spanish-onnx", exist_ok=True)
api.upload_folder(folder_path="./tucuy-onnx-quantized", repo_id="analuciahm/tucuy-fake-news-spanish-onnx", repo_type="model")
print("ONNX subido!")
