import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


async def web_search(query: str, max_results: int = 5) -> str:
    results = DDGS().text(query, max_results=max_results)
    lines = []
    for r in results:
        lines.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
    return "\n".join(lines) or "No results found."


async def fetch_page(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:200])
