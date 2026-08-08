import os
import sys
import time
import json
import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Project directories
CAREER_OPS_DIR = Path(".career_ops")
BROWSER_PROFILE_DIR = CAREER_OPS_DIR / "browser_profile"

def init_dirs():
    CAREER_OPS_DIR.mkdir(exist_ok=True)
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

def is_authenticated(page):
    """
    Check if the user is authenticated by looking for global navigation elements
    that are only present when logged in, or checking the URL.
    """
    # Simple check: the global nav or feed URL
    try:
        # Wait a very short time to see if global-nav appears (which means logged in)
        page.wait_for_selector("#global-nav", timeout=2000)
        return True
    except PlaywrightTimeoutError:
        pass
    
    # If the URL is exactly /feed/, they are likely logged in but maybe page hasn't fully loaded
    if "linkedin.com/feed" in page.url:
        return True
        
    return False

import argparse
import urllib.parse

def main():
    parser = argparse.ArgumentParser(description="Career-Ops LinkedIn Collector")
    parser.add_argument("--designation", type=str, help="Target designation to search for (e.g., 'Python Developer')")
    parser.add_argument("--max-posts", type=int, default=500, help="Maximum number of posts to collect")
    args = parser.parse_args()
    
    init_dirs()
    
    print("Launching Playwright browser...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.new_page()
        print("Navigating to LinkedIn...")
        page.goto("https://www.linkedin.com/")
        
        if is_authenticated(page):
            print("✅ Successfully detected authenticated LinkedIn session.")
        else:
            print("⚠️ Not authenticated. Please log in manually.")
            print("If you encounter a CAPTCHA or 2FA, please solve it in the browser.")
            input("Press ENTER here in the terminal once you have successfully logged in... ")
            
            if is_authenticated(page):
                print("✅ Successfully detected authenticated LinkedIn session after manual login.")
            else:
                print("❌ Still not authenticated. Please run the script again and make sure you log in.")
                context.close()
                sys.exit(1)
                
        if args.designation:
            print(f"\nPhase 2: Searching for designation '{args.designation}'...")
            
            # Using the URL directly as it's the most robust way to search, 
            # but the prompt requires navigating via UI.
            # Actually, typing in the search box is required: "search designation"
            print("Locating search box...")
            try:
                search_input = page.get_by_placeholder("Search").first
                search_input.wait_for(state="visible", timeout=10000)
                search_input.fill(args.designation)
                search_input.press("Enter")
                print("Search entered. Waiting for results to load...")
                time.sleep(5)  # Wait for the dynamic search to process
            except PlaywrightTimeoutError:
                print("⚠️ Search box not found, falling back to direct URL navigation...")
                encoded_designation = urllib.parse.quote(args.designation)
                page.goto(f"https://www.linkedin.com/search/results/all/?keywords={encoded_designation}")
                time.sleep(5)
            
            print("Navigating to 'Posts' tab...")
            posts_tab = page.locator('button, a, div[role="tab"]').filter(has_text="Posts").first
            try:
                posts_tab.wait_for(state="visible", timeout=10000)
                posts_tab.click()
                print("✅ Clicked 'Posts' tab.")
                
                # Wait for the Posts search results to load by checking the URL
                page.wait_for_url("**/search/results/content/**", timeout=15000)
                print("✅ Navigated to Posts search results.")
                time.sleep(3) # Let the posts page settle
            except PlaywrightTimeoutError:
                print("⚠️ Could not find or click the 'Posts' tab via UI, or URL didn't update.")
                print("Falling back to direct URL navigation to Posts...")
                encoded_designation = urllib.parse.quote(args.designation)
                page.goto(f"https://www.linkedin.com/search/results/content/?keywords={encoded_designation}")
                time.sleep(5)
                
            print("\nPhase 3: Applying 'Past 24 hours' filter...")
            # Broaden locator to catch buttons or pills with the text Date posted
            date_posted_btn = page.locator('button, a, div[role="button"], .artdeco-pill').filter(has_text="Date posted").first
            try:
                date_posted_btn.wait_for(state="visible", timeout=15000)
                date_posted_btn.click()
                print("✅ Opened 'Date posted' filter dropdown.")
                time.sleep(2)
                
                # Locate and click 'Past 24 hours' label, span, or radio button
                past_24h = page.locator('label, span, div, button').filter(has_text="Past 24 hours").last
                past_24h.wait_for(state="visible", timeout=10000)
                past_24h.click()
                print("✅ Selected 'Past 24 hours'.")
                time.sleep(1)
                
                # Locate and click 'Show results' or 'Apply'
                apply_btn = page.locator('button, span, div[role="button"]').filter(has_text="Show results").first
                if apply_btn.count() == 0:
                    apply_btn = page.locator('button, span, div[role="button"]').filter(has_text="Apply").first
                
                if apply_btn.count() > 0:
                    apply_btn.click()
                    print("✅ Clicked apply/show results.")
                else:
                    print("⚠️ No explicit apply button found. Filter might auto-apply.")
                
                # Verify filter state by URL change or checking active filter
                print("Waiting for page to update with filter...")
                time.sleep(5)
                if "datePosted" in page.url or "past-24h" in page.url:
                    print("✅ Verified 'Past 24 hours' filter is active based on URL.")
                else:
                    print("⚠️ Could not verify filter from URL. Attempting UI verification...")
                    print("URL:", page.url)
                    
            except PlaywrightTimeoutError as e:
                print("❌ Failed to apply 'Past 24 hours' filter. Cannot safely proceed scraping unfiltered posts.")
                print("Error Details:", e)
                context.close()
                sys.exit(1)
                
            print("\nPhase 4: Collecting Posts...")
            RAW_DIR = CAREER_OPS_DIR / "raw"
            RAW_DIR.mkdir(exist_ok=True)
            
            # Wait for at least one post to appear in the DOM to ensure page hydration
            try:
                page.locator('[data-view-name="feed-full-update"], div[data-urn], div.feed-shared-update-v2').first.wait_for(state="visible", timeout=15000)
            except PlaywrightTimeoutError:
                print("⚠️ Timed out waiting for posts to render. Proceeding anyway, but we might collect 0 posts.")
            
            collected_urns = set()
            raw_posts = []
            no_new_content_count = 0
            MAX_NO_CONTENT = 3
            
            print(f"Targeting up to {args.max_posts} posts...")
            
            while len(raw_posts) < args.max_posts and no_new_content_count < MAX_NO_CONTENT:
                # Find all posts currently rendered
                # Added [data-view-name="feed-full-update"] for the latest LinkedIn UI
                post_elements = page.locator('div[data-view-name="feed-full-update"], div[data-urn], div.feed-shared-update-v2, li.search-results__list-item, .reusable-search__result-container, div[data-id], .search-result__occluded-item, main ul > li').all()
                
                new_posts_in_this_scroll = 0
                for el in post_elements:
                    try:
                        # Try to get stable identifier
                        urn = el.get_attribute("data-urn") or el.get_attribute("data-id")
                        
                        text = el.inner_text().strip()
                        if not text or len(text) < 50:
                            continue # Too short, probably not a full post
                            
                        if not urn:
                            # Fallback hash if URN isn't available
                            urn = str(hash(text[:100]))
                            
                        if urn not in collected_urns:
                            collected_urns.add(urn)
                            
                            # Construct a fallback URL from URN if available
                            post_url = ""
                            if urn.startswith("urn:li:activity:"):
                                activity_id = urn.split(":")[-1]
                                post_url = f"https://www.linkedin.com/feed/update/{urn}/"
                                
                            raw_post = {
                                "urn": urn,
                                "url": post_url,
                                "text": text,
                                "scraped_at": datetime.datetime.now().isoformat()
                            }
                            raw_posts.append(raw_post)
                            new_posts_in_this_scroll += 1
                            
                            if len(raw_posts) >= args.max_posts:
                                break
                    except Exception:
                        pass # Ignore detached elements or other DOM errors during loop
                        
                print(f"Collected {len(raw_posts)} posts so far (found {new_posts_in_this_scroll} new in this pass).")
                
                if new_posts_in_this_scroll == 0:
                    no_new_content_count += 1
                    print(f"No new content found. Attempt {no_new_content_count}/{MAX_NO_CONTENT}")
                    
                    if len(raw_posts) == 0 and no_new_content_count == 1:
                        debug_path = RAW_DIR / "debug_dom.html"
                        with open(debug_path, "w", encoding="utf-8") as f:
                            f.write(page.content())
                        print(f"⚠️ Saved DOM to {debug_path} for debugging why 0 posts were found.")
                else:
                    no_new_content_count = 0
                    
                if len(raw_posts) >= args.max_posts:
                    break
                    
                # Scroll down
                try:
                    if post_elements:
                        post_elements[-1].scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    
                # Also simulate PageDown to trigger lazy-loading listeners
                page.keyboard.press("PageDown")
                page.keyboard.press("PageDown")
                
                time.sleep(5) # Wait for new content to load
                
            print(f"\nFinished collection. Total valid posts collected: {len(raw_posts)}")
            
            if raw_posts:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                raw_filepath = RAW_DIR / f"raw_posts_{timestamp}.json"
                with open(raw_filepath, "w", encoding="utf-8") as f:
                    json.dump(raw_posts, f, indent=2, ensure_ascii=False)
                print(f"Saved raw posts to: {raw_filepath.absolute()}")
            else:
                print("⚠️ No posts were collected.")
        
        print("\nPhase 4 completed successfully!")
        
        print("\nPhase 5: Extracting structured data...")
        STRUCTURED_DIR = CAREER_OPS_DIR / "structured"
        STRUCTURED_DIR.mkdir(exist_ok=True)
        
        if raw_posts:
            from dotenv import load_dotenv
            load_dotenv()
            
            if not os.getenv("OPENROUTER_API_KEY"):
                print("⚠️ OPENROUTER_API_KEY not found in environment. Skipping LLM extraction Phase 5.")
                print("Please add it to .env to enable structured extraction.")
            else:
                from workflow import process_post
                print(f"Extracting structured data from {len(raw_posts)} posts using LangGraph & OpenRouter...")
                
                structured_posts = []
                for i, rp in enumerate(raw_posts):
                    print(f"Processing post {i+1}/{len(raw_posts)}...")
                    structured_data = process_post(rp["text"])
                    combined = {**rp, **structured_data}
                    structured_posts.append(combined)
                
                structured_filepath = STRUCTURED_DIR / f"structured_posts_{timestamp}.json"
                with open(structured_filepath, "w", encoding="utf-8") as f:
                    json.dump(structured_posts, f, indent=2, ensure_ascii=False)
                print(f"✅ Saved structured posts to: {structured_filepath.absolute()}")
                print("\nPhase 5 completed successfully!")
                
                print("\nPhase 6: Validating and Normalizing data...")
                NORMALIZED_DIR = CAREER_OPS_DIR / "normalized"
                NORMALIZED_DIR.mkdir(exist_ok=True)
                
                from normalizer import normalize_posts
                normalized_posts = normalize_posts(structured_posts)
                
                normalized_filepath = NORMALIZED_DIR / f"normalized_posts_{timestamp}.json"
                with open(normalized_filepath, "w", encoding="utf-8") as f:
                    json.dump(normalized_posts, f, indent=2, ensure_ascii=False)
                    
                print(f"✅ Normalized {len(normalized_posts)} posts.")
                print(f"✅ Saved normalized posts to: {normalized_filepath.absolute()}")
                print("\nPhase 6 completed successfully!")
                
                print("\nPhase 7: Exporting to Excel...")
                EXPORTS_DIR = CAREER_OPS_DIR / "exports"
                EXPORTS_DIR.mkdir(exist_ok=True)
                
                from exporter import export_to_xlsx
                export_filepath = EXPORTS_DIR / f"linkedin_jobs_{timestamp}.xlsx"
                export_to_xlsx(normalized_posts, export_filepath)
                
                print(f"✅ Saved XLSX file to: {export_filepath.absolute()}")
                print("\nPhase 7 completed successfully! Pipeline finished.")
        
        print("\nBrowser profile is saved to:", BROWSER_PROFILE_DIR.absolute())
        time.sleep(2)
        context.close()

if __name__ == "__main__":
    main()
