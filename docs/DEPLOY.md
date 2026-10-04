# Deploy for free on Hugging Face Spaces

Hugging Face Spaces runs Docker apps on a free CPU. No credit card needed.

1. Create a free account at https://huggingface.co.
2. Click **New Space**. Give it a name such as `it-ticket-reply-drafter`.
3. Choose **Docker** as the SDK and **Blank** as the template. Keep the free **CPU basic** hardware. Set it to **Public**.
4. Upload all the project files (or push them with git, as the Space page shows).
5. In the Space, open **Settings**, then **Variables and secrets**, and add a **secret** named `GEMINI_API_KEY` with your key. Secrets are never shown in the code or to visitors.
6. Edit the Space's `README.md` and make sure it starts with this header (Hugging Face reads it to know how to run the app):

```
---
title: IT Ticket Reply Drafter
emoji: 🎫
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---
```

7. The Space builds the Docker image and starts the app. When the status shows **Running**, your link works.

Free Spaces go to sleep when nobody uses them for a while and take a short time to wake on the next visit. Open the link yourself before you send it to a company.

## Keep the GitHub repo as the main copy

Push the code to GitHub first, then to the Space. The GitHub repo is what employers read. The Space is the live demo you link from the README.

Do not add the Hugging Face header above to the GitHub README. It only belongs in the Space.
