import aiohttp
import asyncio
import base64
from urllib.parse import urlparse


async def parse_github_url(url):
    parsed_url = urlparse(url)
    path_segments = parsed_url.path.strip("/").split("/")
    if len(path_segments) >= 2:
        owner, repo = path_segments[0], path_segments[1]
        return owner, repo
    else:
        raise ValueError("Invalid GitHub URL provided!")


async def fetch_repo_content(session, owner, repo, path="", token=None):
    base_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with session.get(base_url, headers=headers) as response:
        if response.status == 200:
            return await response.json()
        else:
            response.raise_for_status()


def get_file_content(file_info):
    if file_info["encoding"] == "base64":
        return base64.b64decode(file_info["content"]).decode("utf-8")
    else:
        return file_info["content"]


async def build_directory_tree(session, owner, repo, path="", token=None, indent=0):
    items = await fetch_repo_content(session, owner, repo, path, token)
    tree_str = ""
    file_fetch_tasks = []
    for item in items:
        if ".github" in item["path"].split("/"):
            continue
        if item["type"] == "dir":
            tree_str += "    " * indent + f"[{item['name']}/]\n"
            sub_tree_str, _ = await build_directory_tree(
                session, owner, repo, item["path"], token, indent + 1
            )
            tree_str += sub_tree_str
        else:
            tree_str += "    " * indent + f"{item['name']}\n"
            if item["name"].endswith(
                (".py", ".ipynb", ".html", ".css", ".js", ".jsx", ".rst", ".md")
            ):
                file_fetch_tasks.append(
                    fetch_repo_content(session, owner, repo, item["path"], token)
                )

    file_contents = await asyncio.gather(*file_fetch_tasks)
    file_contents_decoded = [get_file_content(file_info) for file_info in file_contents]

    return tree_str, file_contents_decoded


async def retrieve_github_repo_info(url, token=None):
    owner, repo = await parse_github_url(url)

    async with aiohttp.ClientSession() as session:
        try:
            readme_info = await fetch_repo_content(
                session, owner, repo, "README.md", token
            )
            readme_content = get_file_content(readme_info)
            formatted_string = f"README.md:\n```\n{readme_content}\n```\n\n"
        except Exception as e:
            formatted_string = "README.md: Not found or error fetching README\n\n"

        directory_tree, file_contents = await build_directory_tree(
            session, owner, repo, token=token
        )
        formatted_string += f"Directory Structure:\n{directory_tree}\n"

        for file_content in file_contents:
            formatted_string += "\n" + "```" + file_content + "```" + "\n"

    return formatted_string


async def main():
    github_url = "https://github.com/nomic-ai/nomic/tree/main"
    token = "Your Github access token here"  # Replace with your actual token

    _, repo = await parse_github_url(github_url)

    formatted_repo_info = await retrieve_github_repo_info(github_url, token=token)
    output_file_name = f"{repo}-formatted-prompt.txt"

    with open(output_file_name, "w", encoding="utf-8") as file:
        file.write(formatted_repo_info)

    print(f"Repository information has been saved to {output_file_name}")


if __name__ == "__main__":
    asyncio.run(main())
