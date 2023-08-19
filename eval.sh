MODEL_NAME=NousResearch/Llama-2-7b-hf

python generate_run_spec.py --model $MODEL_NAME
helm-run --conf-paths run_spec_llm_efficiency.conf --enable-huggingface-models $MODEL_NAME --suite v1 --num-threads 1 -m 1000
echo "helm-summarize --suite v1"
echo "helm-server to see result"