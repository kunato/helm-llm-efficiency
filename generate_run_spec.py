import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str)
    args = parser.parse_args()
    with open('run_spec_llm_efficiency.conf.template') as f:
        lines = f.read()
    lines = lines.replace('model=text', f'model={args.model}')
    with open('run_spec_llm_efficiency.conf', 'w') as w:
        w.write(lines)


if __name__ == "__main__":
    main()