# Push this project to your own public GitHub repo

## 1. Re-authenticate GitHub CLI (if you use it)

```bash
gh auth login -h github.com
```

Follow the prompts (browser or token).

## 2. Create a new public repo and push

**Option A – Using GitHub CLI**

```bash
gh repo create Cactus-Hackathon --public --source=. --remote=myorigin --push
```

This creates `https://github.com/YOUR_USERNAME/Cactus-Hackathon` and pushes your current branch.

**Option B – Using the GitHub website**

1. Go to https://github.com/new
2. Repository name: `Cactus-Hackathon` (or any name)
3. Set visibility to **Public**
4. Do **not** add a README, .gitignore, or license (this repo already has them)
5. Create the repository
6. In this project folder, add your new repo and push:

```bash
git remote add myorigin https://github.com/YOUR_USERNAME/Cactus-Hackathon.git
git push -u myorigin main
```

Replace `YOUR_USERNAME` with your GitHub username.

## Note

Current `origin` points to the Cactus template repo. The steps above add a second remote (`myorigin`) so you keep the original `origin` and push your code to your own public repo.
