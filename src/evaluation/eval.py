from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
 
tokenizer_name = "ESGBERT/EnvironmentalBERT-environmental"
model_name = "ESGBERT/EnvironmentalBERT-environmental"
 
model = AutoModelForSequenceClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, max_len=512)
 
pipe = pipeline("text-classification", model=model, tokenizer=tokenizer) # set device=0 to use GPU
 
# See https://huggingface.co/docs/transformers/main_classes/pipelines#transformers.pipeline
print(pipe("Scope 1 emissions are reported here on a like-for-like basis against the 2013 baseline and exclude emissions from additional vehicles used during repairs.", padding=True, truncation=True))

#output
#[{'label': 'environmental', 'score': 0.9979760050773621}]

