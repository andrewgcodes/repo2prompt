import aiohttp
import asyncio
import base64
from urllib.parse import urlparse
import time
import backoff
from typing import Tuple, Dict, Any, Optional


async def parse_github_url(url: str) -> Tuple[str, str]:
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.strip("/").split("/")
    if len(path_segments) >= 2:
        return path_segments[0], path_segments[1]
    else:
        raise ValueError("Invalid GitHub URL provided!")


@backoff.on_exception(
    backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=8
)
async def fetch_rate_limit_status(
    session: aiohttp.ClientSession, token: str
) -> Dict[str, Any]:
    rate_limit_url = "https://api.github.com/rate_limit"
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(rate_limit_url, headers=headers) as response:
        rate_limit_data = await response.json()
        return rate_limit_data["rate"]


@backoff.on_exception(
    backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=8
)
async def fetch_repo_content(
    session: aiohttp.ClientSession,
    owner: str,
    repo: str,
    path: str = "",
    token: Optional[str] = None,
) -> Any:
    base_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with session.get(base_url, headers=headers) as response:
        if response.status == 200:
            return await response.json()
        elif response.status in {403, 429}:
            retry_after = response.headers.get("Retry-After", None)
            if retry_after:
                print(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                await asyncio.sleep(int(retry_after))
                return await fetch_repo_content(session, owner, repo, path, token)
            else:
                raise aiohttp.ClientError(
                    f"Rate limit exceeded with status {response.status}. No Retry-After header provided."
                )
        elif response.status == 404:
            raise aiohttp.ClientError("Resource not found.")
        else:
            response.raise_for_status()


def get_file_content(file_info: Dict[str, Any]) -> str:
    if file_info["encoding"] == "base64":
        return base64.b64decode(file_info["content"]).decode("utf-8")
    else:
        return file_info["content"]


async def build_directory_tree(
    semaphore: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    owner: str,
    repo: str,
    path: str = "",
    token: Optional[str] = None,
    indent: int = 0,
) -> str:
    items = await fetch_repo_content(session, owner, repo, path, token)
    tree_str = ""
    tasks = []
    for item in items:
        if ".github" in item["path"].split("/"):
            continue
        if item["type"] == "dir":
            tree_str += "    " * indent + f"[{item['name']}/]\n"
            task = asyncio.create_task(
                build_directory_tree(
                    semaphore, session, owner, repo, item["path"], token, indent + 1
                )
            )
            tasks.append(task)
        else:
            tree_str += "    " * indent + f"{item['name']}\n"
            if item["name"].endswith(
                (".py", ".ipynb", ".html", ".css", ".js", ".jsx", ".rst", ".md")
            ):
                async with semaphore:
                    file_info = await fetch_repo_content(
                        session, owner, repo, item["path"], token
                    )
                    file_content = get_file_content(file_info)
                    tree_str += (
                        "    " * (indent + 1) + "```" + file_content + "```" + "\n"
                    )

    for task in tasks:
        tree_str += await task
    return tree_str


async def retrieve_github_repo_info(url: str, token: Optional[str] = None) -> str:
    owner, repo = await parse_github_url(url)
    async with aiohttp.ClientSession() as session:
        try:
            if token is not None:
                rate = await fetch_rate_limit_status(session, token)
                print(f"Rate Limit Status: {rate['remaining']} / {rate['limit']}")
                if rate["remaining"] < 100:
                    reset_time = rate["reset"]
                    now = time.time()
                    if reset_time > now:
                        sleep_duration = reset_time - now
                        print(
                            f"Approaching rate limit. Sleeping for {sleep_duration} seconds."
                        )
                        await asyncio.sleep(sleep_duration)
            else:
                print(
                    "Warning: No token provided. Proceeding without rate limit status check."
                )

            semaphore = asyncio.Semaphore(100)  # Limiting to 100 concurrent requests
            formatted_string = ""
            if token is not None:
                readme_info = await fetch_repo_content(
                    session, owner, repo, "README.md", token
                )
            else:
                raise ValueError("Token is required for fetching repo content.")

            readme_content = get_file_content(readme_info)
            formatted_string += f"README.md:\n```\n{readme_content}\n```\n\n"
        except Exception as e:
            formatted_string = f"Failed to retrieve README.md: {e}\n\n"

        try:
            if token is not None:
                directory_tree = await build_directory_tree(
                    semaphore, session, owner, repo, token=token
                )
            else:
                raise ValueError("Token is required for building directory tree.")

            formatted_string += f"Directory Structure:\n{directory_tree}\n"
        except Exception as e:
            formatted_string += f"Failed to build directory tree: {e}\n"

    return formatted_string


async def main():
    github_url = "https://github.com/nomic-ai/nomic/tree/main" # Replace with repo url
    token = "Your Github access token here"  # Replace with your token

    if not token or token == "Your Github access token here":
        print("Error: Please provide a valid GitHub access token.")
        return

    try:
        _, repo = await parse_github_url(github_url)
        formatted_repo_info = await retrieve_github_repo_info(github_url, token=token)
        output_file_name = f"{repo}-formatted-prompt.txt"

        with open(output_file_name, "w", encoding="utf-8") as file:
            file.write(formatted_repo_info)

        print(f"Repository information has been saved to {output_file_name}")
    except Exception as e:
        print(f"Failed to retrieve repository information: {e}")


if __name__ == "__main__":
    asyncio.run(main())
