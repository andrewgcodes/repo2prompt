import os
import base64
from urllib.parse import urlparse
from typing import Optional
from tqdm import tqdm
from typing import List, Dict, Any
import asyncio
import aiohttp
from .types import RateLimitExceeded
import time

def parse_github_url(url):
    """
    Parses your GitHub URL and extracts the repository owner and name.
    """
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.strip("/").split("/")
    if len(path_segments) >= 2:
        owner, repo = path_segments[0], path_segments[1]
        return owner, repo
    else:
        raise ValueError("Invalid GitHub URL provided!")

async def fetch_repo_content(owner, repo, path='', token=None):
    """
    Fetches the content of your GitHub repository.
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with aiohttp.ClientSession() as session:
        async with session.get(base_url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                if response.status == 403:
                    raise RateLimitExceeded
                
                else:
                    raise Exception(f"Error fetching content: {response.status}")

def get_file_content(file_info):
    """
    Retrieves and decodes the content of files
    """
    if file_info['encoding'] == 'base64':
        return base64.b64decode(file_info['content']).decode('utf-8')
    else:
        return file_info['content']



async def build_directory_tree(
    owner: str,
    repo: str,
    path: str = '',
    token: Optional[str] = None,
    indent: int = 0,
    file_paths: List[tuple[int, str]] = [],
    is_base: bool = False
) -> tuple[str, List[tuple[int, str]]]:
    
    async def process_item(item: Dict[str, Any], tree_str: str, file_paths: List[tuple[int, str]], indent: int) -> tuple[str, List[tuple[int, str]]]:
        if '.github' in item['path'].split('/'):
            pass
        if item['type'] == 'dir':
            tree_str += ' ' * indent + f"[{item['name']}/]\n"
            tree_str += (await build_directory_tree(owner, repo, item['path'], token, indent + 1, file_paths, is_base=False))[0]
        else:
            tree_str += ' ' * indent + f"{item['name']}\n"
            # Indicate which file extensions should be included in the prompt!
            if item['name'].endswith(('.py', '.ipynb', '.html', '.css', '.js', '.jsx', '.rst', '.md', '.rs',)):
                file_paths.append((indent, item['path']))
        return tree_str, file_paths

    items = await fetch_repo_content(owner, repo, path, token)
    if items is None:
        return "", file_paths
    tree_str = ""
    tasks = [process_item(item, "", file_paths, indent) for item in items]
    file_paths = []
    tree_str = ""
    if is_base:
        for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Building tree"):
            res = await future
            tree_str += res[0]
            file_paths.extend(res[1])
    else:
        for future in asyncio.as_completed(tasks):
            res = await future
            tree_str += res[0]
            file_paths.extend(res[1])
    return tree_str, file_paths
                                            
async def fetch_file_content(args, semaphore) -> str:
    owner, repo, path, token, indent = args
    async with semaphore:
        file_info = await fetch_repo_content(owner, repo, path, token)
        file_content = get_file_content(file_info)
        return '\n' + ' ' * indent + f"{path}:\n" + ' ' * indent + '\n' + file_content + '\n' + ' ' * indent + '\n'

async def fetch_file_contents(owner, repo, file_paths, github_token, concurrency) -> str:
    semaphore = asyncio.Semaphore(concurrency)  # Limit the number of concurrent file fetches
    tasks = [
        fetch_file_content(
            (owner, repo, path, github_token, indent), semaphore
        ) 
        for indent, path in file_paths
    ]

    # we use asyncio.gather to ensure the order of results matches the order of tasks
    formatted_contents = await asyncio.gather(*tasks)
    return ''.join(formatted_contents)

async def extract_repo(
    github_url: str,
    github_token: Optional[str] = None,
    max_concurrent_requests: int = 100
) -> tuple[str, str]:
    '''
    Args:
    github_url : str,  A URL to a Github repository, must use tree/main or tree/branch_name
    github_token : Optional[str],  A Github personal access token, if not provided will use the GITHUB_TOKEN env variable
    max_concurrent_requests : int,  The number of concurrent files that are being read
    Returns:
    str : A string representation of the repository information, suitable for use in a prompt
    '''
    if github_token is None:
        github_token = os.getenv("GITHUB_TOKEN")
    if github_url.split('/')[-2] != 'tree':
        raise ValueError(
    "Please provide a URL that ends with 'tree', 'tree/main', or 'tree/branch_name'. "
    f"Got URL: {github_url}"
    )
    owner, repo = parse_github_url(github_url)
   
    readme_info = await fetch_repo_content(owner, repo, 'README.md', github_token)
    readme_content = get_file_content(readme_info)
    formatted_string = f"README.md:\n\n{readme_content}\n\n\n"

    t0 = time.time()
    directory_tree, file_paths = await build_directory_tree(owner, repo, token=github_token, is_base=True)
    print(f"Time in build_directory_tree: {time.time() - t0:.2f} seconds")
    t0 = time.time()
    formatted_string += await fetch_file_contents(
        owner, repo, file_paths, github_token, max_concurrent_requests
    )
    print(f"Time in fetch_file_contents: {time.time() - t0:.2f} seconds")
    return formatted_string, directory_tree                                    
