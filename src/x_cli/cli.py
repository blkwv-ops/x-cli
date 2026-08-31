"""Click CLI for x-cli."""

from __future__ import annotations

import json
import subprocess
import sys

import click

from .api import XApiClient
from .auth import load_credentials
from .formatters import format_output
from .utils import parse_tweet_id, strip_at


def _resolve_media_ids(client: XApiClient, media_path: str | None) -> list[str] | None:
    """Upload a media file and return a single-element media_ids list, or None."""
    if not media_path:
        return None
    print(f"Uploading {media_path}…", file=sys.stderr)
    media_id = client.upload_media(media_path)
    print(f"Upload complete (media_id={media_id})", file=sys.stderr)
    return [media_id]


class State:
    def __init__(self, mode: str, verbose: bool = False) -> None:
        self.mode = mode
        self.verbose = verbose
        self._client: XApiClient | None = None

    @property
    def client(self) -> XApiClient:
        if self._client is None:
            creds = load_credentials()
            self._client = XApiClient(creds)
        return self._client

    def output(self, data, title: str = "") -> None:
        format_output(data, self.mode, title, verbose=self.verbose)


pass_state = click.make_pass_decorator(State)


@click.group()
@click.option("--json", "-j", "fmt", flag_value="json", help="JSON output")
@click.option("--plain", "-p", "fmt", flag_value="plain", help="TSV output for piping")
@click.option("--markdown", "-md", "fmt", flag_value="markdown", help="Markdown output")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output (show metrics, timestamps, metadata)")
@click.pass_context
def cli(ctx, fmt, verbose):
    """x-cli: CLI for X/Twitter API v2."""
    ctx.ensure_object(dict)
    ctx.obj = State(fmt or "human", verbose=verbose)


# ============================================================
# tweet
# ============================================================

@cli.group()
def tweet():
    """Tweet operations."""


@tweet.command("post")
@click.argument("text")
@click.option("--media", "media_path", default=None, type=click.Path(exists=True), help="Path to image or video file to attach")
@click.option("--poll", default=None, help="Comma-separated poll options")
@click.option("--poll-duration", default=1440, type=int, help="Poll duration in minutes")
@pass_state
def tweet_post(state, text, media_path, poll, poll_duration):
    """Post a tweet, optionally with an image or video attachment."""
    media_ids = _resolve_media_ids(state.client, media_path)
    poll_options = [o.strip() for o in poll.split(",")] if poll else None
    data = state.client.post_tweet(text, poll_options=poll_options, poll_duration_minutes=poll_duration, media_ids=media_ids)
    state.output(data, "Posted")


@tweet.command("get")
@click.argument("id_or_url")
@pass_state
def tweet_get(state, id_or_url):
    """Fetch a tweet by ID or URL."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.get_tweet(tid)
    state.output(data, f"Tweet {tid}")


@tweet.command("delete")
@click.argument("id_or_url")
@pass_state
def tweet_delete(state, id_or_url):
    """Delete a tweet."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.delete_tweet(tid)
    state.output(data, "Deleted")


@tweet.command("reply")
@click.argument("id_or_url")
@click.argument("text")
@click.option("--media", "media_path", default=None, type=click.Path(exists=True), help="Path to image or video file to attach")
@pass_state
def tweet_reply(state, id_or_url, text, media_path):
    """Reply to a tweet."""
    tid = parse_tweet_id(id_or_url)
    media_ids = _resolve_media_ids(state.client, media_path)
    data = state.client.post_tweet(text, reply_to=tid, media_ids=media_ids)
    state.output(data, "Reply")


@tweet.command("quote")
@click.argument("id_or_url")
@click.argument("text")
@click.option("--media", "media_path", default=None, type=click.Path(exists=True), help="Path to image or video file to attach")
@pass_state
def tweet_quote(state, id_or_url, text, media_path):
    """Quote tweet."""
    tid = parse_tweet_id(id_or_url)
    media_ids = _resolve_media_ids(state.client, media_path)
    data = state.client.post_tweet(text, quote_tweet_id=tid, media_ids=media_ids)
    state.output(data, "Quote")


@tweet.command("search")
@click.argument("query")
@click.option("--max", "max_results", default=10, type=int, help="Max results (10-100)")
@pass_state
def tweet_search(state, query, max_results):
    """Search recent tweets."""
    data = state.client.search_tweets(query, max_results)
    state.output(data, f"Search: {query}")


@tweet.command("metrics")
@click.argument("id_or_url")
@pass_state
def tweet_metrics(state, id_or_url):
    """Get tweet engagement metrics."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.get_tweet_metrics(tid)
    state.output(data, f"Metrics {tid}")


# ============================================================
# user
# ============================================================

@cli.group()
def user():
    """User operations."""


@user.command("get")
@click.argument("username")
@pass_state
def user_get(state, username):
    """Look up a user profile."""
    data = state.client.get_user(strip_at(username))
    state.output(data, f"@{strip_at(username)}")


@user.command("timeline")
@click.argument("username")
@click.option("--max", "max_results", default=10, type=int, help="Max results (5-100)")
@pass_state
def user_timeline(state, username, max_results):
    """Fetch a user's recent tweets."""
    uname = strip_at(username)
    user_data = state.client.get_user(uname)
    uid = user_data["data"]["id"]
    data = state.client.get_timeline(uid, max_results)
    state.output(data, f"@{uname} timeline")


@user.command("followers")
@click.argument("username")
@click.option("--max", "max_results", default=100, type=int, help="Max results (1-1000)")
@pass_state
def user_followers(state, username, max_results):
    """List a user's followers."""
    uname = strip_at(username)
    user_data = state.client.get_user(uname)
    uid = user_data["data"]["id"]
    data = state.client.get_followers(uid, max_results)
    state.output(data, f"@{uname} followers")


@user.command("following")
@click.argument("username")
@click.option("--max", "max_results", default=100, type=int, help="Max results (1-1000)")
@pass_state
def user_following(state, username, max_results):
    """List who a user follows."""
    uname = strip_at(username)
    user_data = state.client.get_user(uname)
    uid = user_data["data"]["id"]
    data = state.client.get_following(uid, max_results)
    state.output(data, f"@{uname} following")


# ============================================================
# me
# ============================================================

@cli.group()
def me():
    """Self operations (authenticated user)."""


@me.command("mentions")
@click.option("--max", "max_results", default=10, type=int, help="Max results (5-100)")
@pass_state
def me_mentions(state, max_results):
    """Fetch your recent mentions."""
    data = state.client.get_mentions(max_results)
    state.output(data, "Mentions")


@me.command("bookmarks")
@click.option("--max", "max_results", default=10, type=int, help="Max results (1-100)")
@pass_state
def me_bookmarks(state, max_results):
    """Fetch your bookmarks."""
    data = state.client.get_bookmarks(max_results)
    state.output(data, "Bookmarks")


@me.command("bookmark")
@click.argument("id_or_url")
@pass_state
def me_bookmark(state, id_or_url):
    """Bookmark a tweet."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.bookmark_tweet(tid)
    state.output(data, "Bookmarked")


@me.command("unbookmark")
@click.argument("id_or_url")
@pass_state
def me_unbookmark(state, id_or_url):
    """Remove a bookmark."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.unbookmark_tweet(tid)
    state.output(data, "Unbookmarked")


# ============================================================
# stream (experimental)
# ============================================================

@cli.group()
def stream():
    """Streaming operations (experimental)."""


@stream.command("accounts")
@click.argument("usernames", nargs=-1, required=True)
@click.option("--max-tweets", default=0, type=int, help="Stop after N tweets (0 = run until Ctrl+C)")
@click.option("--replace-rules", is_flag=True, default=False, help="Delete existing filtered stream rules before adding this one")
@click.option("--discord", "discord_channel", default=None, help="Discord webhook URL or channel ID to forward tweets")
@pass_state
def stream_accounts(state, usernames, max_tweets, replace_rules, discord_channel):
    """Stream tweets in near real-time from specific accounts.

    Example:

        x-cli stream accounts TradeHawk DeItaone tradfi

    Forward to Discord:

        x-cli stream accounts TradeHawk DeItaone --discord 1276561751441281097
    """
    handles = [strip_at(u) for u in usernames]
    rule = " OR ".join(f"from:{h}" for h in handles) + " -is:retweet"

    client = state.client

    if replace_rules:
        print("[x-cli] Deleting existing filtered stream rules…", file=sys.stderr)
        try:
            client.delete_all_stream_rules()
        except Exception as exc:  # pragma: no cover - best-effort logging
            print(f"[x-cli] Warning: failed to delete existing rules: {exc}", file=sys.stderr)

    print(f"[x-cli] Adding filtered stream rule: {rule}", file=sys.stderr)
    client.add_stream_rule(rule, tag="x-cli:accounts")

    if discord_channel:
        print(f"[x-cli] Forwarding tweets to Discord channel {discord_channel}", file=sys.stderr)

    printed = 0
    print("[x-cli] Connected to filtered stream. Press Ctrl+C to stop.", file=sys.stderr)

    params = {
        "tweet.fields": "created_at,author_id,entities,text,note_tweet,referenced_tweets,attachments",
        "expansions": "author_id,referenced_tweets.id,referenced_tweets.id.author_id,attachments.media_keys",
        "user.fields": "name,username,profile_image_url",
        "media.fields": "url,preview_image_url,type,width,height,alt_text",
    }

    import time as _time
    max_backoff = 300  # 5 min cap
    backoff = 1

    while True:
        try:
            for line in client.stream_filtered(params=params):
                # Reset backoff on successful data
                backoff = 1

                # Always print raw JSON to stdout
                print(line)

                # Forward to Discord if configured
                if discord_channel:
                    _forward_to_discord(line, discord_channel)

                printed += 1
                if max_tweets and printed >= max_tweets:
                    return
        except KeyboardInterrupt:  # pragma: no cover - interactive only
            print("[x-cli] Stream interrupted by user", file=sys.stderr)
            return
        except Exception as exc:
            print(f"[x-cli] Stream disconnected: {exc}", file=sys.stderr)
            print(f"[x-cli] Reconnecting in {backoff}s…", file=sys.stderr)
            _time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


def _forward_to_discord(raw_line: str, channel_id: str) -> None:
    """Parse a stream JSON line and send a rich embed to Discord via webhook.

    Uses the DISCORD_WEBHOOK_URL env var or the channel_id as webhook URL.
    Falls back to openclaw CLI if no webhook is configured.
    """
    import os
    import httpx as _httpx

    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return

    data = payload.get("data")
    if not data:
        return

    # Resolve author info from includes
    author_id = data.get("author_id", "")
    username = author_id
    display_name = ""
    includes = payload.get("includes", {})
    for user in includes.get("users", []):
        if user.get("id") == author_id:
            username = user.get("username", author_id)
            display_name = user.get("name", username)
            break
    if not display_name:
        display_name = username

    # Use note_tweet text if available (long tweets), otherwise regular text
    note_tweet = data.get("note_tweet", {})
    text = note_tweet.get("text") or data.get("text", "")
    tweet_id = data.get("id", "")
    created = data.get("created_at", "")

    # Extract cashtags / hashtags if present
    entities = data.get("entities", {})
    cashtags = [c.get("tag", "") for c in entities.get("cashtags", [])]
    hashtags = [h.get("tag", "") for h in entities.get("hashtags", [])]
    tags = []
    if cashtags:
        tags.extend(f"${t}" for t in cashtags)
    if hashtags:
        tags.extend(f"#{t}" for t in hashtags)

    url = f"https://x.com/{username}/status/{tweet_id}"

    # Format timestamp for Discord (convert to EST)
    ts_display = created
    if created:
        try:
            from datetime import datetime, timezone, timedelta
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            est = timezone(timedelta(hours=-5))
            dt_est = dt.astimezone(est)
            ts_display = dt_est.strftime("%-m/%-d/%Y %-I:%M %p")
        except Exception:
            pass

    # X logo (black on white, small)
    x_icon = "https://cdn.cms-twdigitalassets.com/content/dam/about-twitter/x/brand-toolkit/logo-black.png.twimg.2560.png"

    import re

    def _strip_tco(s: str) -> str:
        """Remove t.co links from text."""
        return re.sub(r'\s*https://t\.co/\S+', '', s).strip()

    # Check for quoted tweet
    quoted_block = ""
    quoted_media_url = ""
    referenced = data.get("referenced_tweets", [])
    quoted_ref = next((r for r in referenced if r.get("type") == "quoted"), None)
    if quoted_ref:
        quoted_id = quoted_ref.get("id", "")
        # Find the quoted tweet in includes.tweets
        included_tweets = includes.get("tweets", [])
        for qt in included_tweets:
            if qt.get("id") == quoted_id:
                qt_text = qt.get("text", "")
                qt_note = qt.get("note_tweet", {})
                qt_text = qt_note.get("text") or qt_text
                qt_text = _strip_tco(qt_text)  # clean t.co from quoted text too
                qt_author_id = qt.get("author_id", "")
                qt_username = qt_author_id
                qt_display = ""
                for u in includes.get("users", []):
                    if u.get("id") == qt_author_id:
                        qt_username = u.get("username", qt_author_id)
                        qt_display = u.get("name", qt_username)
                        break
                if not qt_display:
                    qt_display = qt_username
                qt_url = f"https://x.com/{qt_username}/status/{quoted_id}"

                # Check if quoted tweet has media
                qt_media_keys = qt.get("attachments", {}).get("media_keys", [])
                included_media = includes.get("media", [])
                for mk in qt_media_keys:
                    for m in included_media:
                        if m.get("media_key") == mk:
                            quoted_media_url = m.get("url") or m.get("preview_image_url", "")
                            break
                    if quoted_media_url:
                        break

                quoted_block = (
                    f"\n\n> **{qt_display}** (@{qt_username})\n"
                    f"> {qt_text}\n"
                    f"> [View original]({qt_url})"
                )
                break

    # Strip t.co links from main text
    clean_text = _strip_tco(text)

    # Build embed (RedboxGlobal style)
    description = f"**Posted**\n{clean_text}"
    if quoted_block:
        description += quoted_block
    if tags:
        description += "\n\n" + " ".join(tags)
    description += f"\n\n[View on 𝕏]({url})"

    embed = {
        "description": description,
        "color": 15158332,  # red
        "footer": {
            "text": f"𝕏 · {ts_display}",
            "icon_url": x_icon,
        },
    }

    # Attach media (images / video thumbnails)
    media_keys = data.get("attachments", {}).get("media_keys", [])
    included_media = includes.get("media", [])
    images = []
    for mk in media_keys:
        for m in included_media:
            if m.get("media_key") == mk:
                # For photos use url; for video/gif use preview_image_url (thumbnail)
                img_url = m.get("url") or m.get("preview_image_url")
                if img_url:
                    images.append(img_url)
                break

    # If no direct media but quoted tweet has media, use that
    if not images and quoted_media_url:
        images.append(quoted_media_url)

    # Discord embed supports one image; send extras as additional embeds
    extra_embeds = []
    if images:
        embed["image"] = {"url": images[0]}
        for extra_img in images[1:]:
            extra_embeds.append({
                "url": url,  # same URL groups them visually in Discord
                "image": {"url": extra_img},
                "color": 15158332,
            })

    # Resolve profile image URL
    profile_image = ""
    for user in includes.get("users", []):
        if user.get("id") == author_id:
            profile_image = user.get("profile_image_url", "")
            break

    # Determine webhook URL
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url and channel_id.startswith("https://"):
        webhook_url = channel_id

    if webhook_url:
        try:
            all_embeds = [embed] + extra_embeds
            webhook_payload = {
                "username": f"{display_name} (@{username})",
                "avatar_url": profile_image or "https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
                "embeds": all_embeds[:10],  # Discord max 10 embeds
            }
            resp = _httpx.post(
                webhook_url,
                json=webhook_payload,
                timeout=10,
            )
            if resp.status_code >= 400:
                print(f"[x-cli] Discord webhook error: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        except Exception as exc:
            print(f"[x-cli] Discord webhook failed: {exc}", file=sys.stderr)
    else:
        # Fallback to openclaw CLI
        msg = f"**@{username}**\n{text}\n{url}"
        try:
            subprocess.run(
                ["openclaw", "message", "send", "--channel", "discord", "--target", channel_id, "--message", msg],
                capture_output=True,
                timeout=10,
            )
        except Exception as exc:
            print(f"[x-cli] Discord send failed: {exc}", file=sys.stderr)


# ============================================================
# quick actions (top-level)
# ============================================================

@cli.command("like")
@click.argument("id_or_url")
@pass_state
def like(state, id_or_url):
    """Like a tweet."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.like_tweet(tid)
    state.output(data, "Liked")


@cli.command("retweet")
@click.argument("id_or_url")
@pass_state
def retweet(state, id_or_url):
    """Retweet a tweet."""
    tid = parse_tweet_id(id_or_url)
    data = state.client.retweet(tid)
    state.output(data, "Retweeted")


def main():
    cli()


if __name__ == "__main__":
    main()
