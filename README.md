# repo2prompt

This is a simple package with minimal dependencies that turns a Github Repo's contents into a big prompt for long-context models.

this work for repos containing rust, python, javascript containing via the following file types:
'.py', '.ipynb', '.html', '.css', '.js', '.jsx', '.rst', '.md', '.rs'

Example Usage:

```python
from repo2prompt.extraction import extract_repo

extract_repo(github_url="https://github.com/vllm-project/vllm/tree/main", github_token="your_github_token")
```

Or 

```python
from repo2prompt.extraction import extract_repo

extract_repo(github_url="https://github.com/vllm-project/vllm/tree/main") # os.getenv("GITHUB_TOKEN") used internally
```

an important thing to note, github only allows 5000 requests per hour, so be careful

