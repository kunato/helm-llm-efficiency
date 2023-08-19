
# TO setup and run helm
```
1. pip install -e .
2. edit eval.sh (MODEL_NAME=NousResearch/Llama-2-7b-hf) to model in huggingface
3. sh eval.sh
4. helm-summarize --suite v1
5. helm-server
```

# To clean up
```
rm -rf benchmark_output
rm -rf prod_env
```
