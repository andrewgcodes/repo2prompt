# repo2prompt
Turn a Github Repo's contents into a big prompt for long-context models like Claude 3 Opus.

<a target="_blank" href="https://colab.research.google.com/github/andrewgcodes/repo2prompt/blob/main/repo2prompt.ipynb">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

Super easy:
You will need a Github repo URL (public) and a Github access token. You can also use this with private repos but your token will need to have those permissions.

Within the build_directory_tree function, you can specify which file extensions should be included in the output.

The output is saved to a .txt file with name [repo]-formatted-prompt.txt

By the way, Github is limited to 5,000 API requests per hour so if a bug happens, that might be why!
