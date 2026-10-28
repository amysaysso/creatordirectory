CREATOR DIRECTORY - SETUP AND COLUMN GUIDE
==========================================

This turns the PUBLISH Google Sheet into a single web page that search
engines and AI tools can read. Every morning it reads the Sheet, rebuilds
the page, and publishes it. You only ever edit the publish Sheet.

The intake form and its response sheet are never published. Copying a
creator from intake into the publish Sheet is your approval step.


WHAT'S IN THE FOLDER
--------------------
generate.py   Reads the publish Sheet and writes the page.
build.yml     Runs generate.py every morning and publishes the result.


THE PUBLISH SHEET: ONE ROW PER SHOW
-----------------------------------
If a creator has two shows, give each show its own row with the same Name.

Header names must match (capital letters don't matter). Columns can be in
any order, and extra columns are ignored.

HIDDEN (used, never shown)
  Date of Submission/Renewal
      If the same Show Name appears twice, the newest row is used.

SHOWN ON THE CARD
  Name                 "Hosted by ..."
  Show Name            Card title. Rows missing Name or Show Name are skipped.
  Show Description     Under the tags.
  Show Style           Tags + filter. Several allowed, separated by commas:
                       Interviews / guests, Solo, Co-hosted or panel,
                       Storytelling / narrative
                       (If Show Style is blank, the old Format column is
                       used instead. "Hybrid" shows as "Mixed format".)
  Primary Topic        Tag, and searchable. A topic appears in the topic
                       filter once 2 or more shows share it, so tidy similar
                       topics into one wording when you copy entries over.
  Faith                Yes = "Faith-based" tag. Visitors can show only these
                       or hide them. Blank or No = nothing shown.
  Politics             Yes = "Political show" tag. Visitors can show only
                       these or hide them. Blank or No = nothing shown.
  Showcase Video       The full YouTube link. Adds a "Watch the Showcase"
                       button.

LINKS (each becomes a link on the card)
  Website, Listen, YouTube, Newsletter, Instagram, LinkedIn, Facebook,
  Threads, TikTok, Pinterest, X / Twitter, Twitch
      Full links always work. For the social platforms, an @handle also
      works.

  Listen               One direct link to the show on a listening platform
                       (Apple Podcasts, Spotify, or the show's own web
                       player). No link pages like Podlink or Listen.fm.
  RSS                  Never shown. A raw feed is a page of code, so it's
                       only used to tag the show as Audio. Put a real
                       listening link in Listen for every audio show.
  Other Links          Any number of full links in one cell, separated by
                       spaces, commas or new lines. Each is labeled by its
                       web address automatically (bsky.app = "Bluesky",
                       substack.com = "Substack", an unknown site = its own
                       name). A link that's already in another column isn't
                       repeated.

FORMAT IS AUTOMATIC
  The format tags and filter (Audio, Video, Newsletter, Livestream) are
  worked out from the links. There is no column for them.
      Audio       a Listen link, RSS feed, or Spotify/Apple link
      Video       a YouTube link
      Newsletter  a Newsletter, Substack, Patreon or Medium link
      Livestream  a Twitch link


WHEN A NEW SOCIAL PLATFORM COMES ALONG
--------------------------------------
Nothing to change. Creators put the full link in "Other Links" and it
appears on their card, labeled with the site's name.

Only if a platform becomes very common might you want its own column and
a nicer label. That needs a one-line change to generate.py, so ask Claude.


COLUMNS TO ADD TO YOUR CURRENT PUBLISH SHEET
--------------------------------------------
Add these. Keep every existing column and header as it is.
  Show Style
  Politics
  Listen
  X / Twitter
  Other Links
  Showcase Video

Existing creators can stay blank in the new columns until you get to them.


ONE-TIME SETUP (ABOUT 20 MINUTES)
---------------------------------
Same steps as the guest directory, in a new repository.

STEP 1. Get the publish Sheet's CSV link
  File > Share > Publish to web > choose the publish tab > choose
  "Comma-separated values (.csv)" > copy the link.
  (If it's already published another way for the old directory, leave
  that alone and just pick the tab and CSV to get a second link.)

STEP 2. Create the repository
  New repository (for example "creator-directory"), set to Public.
  Upload generate.py and this guide.
  Add file > Create new file > name it  .github/workflows/build.yml
  > paste in the contents of build.yml > Commit changes.

STEP 3. Add the settings
  Settings > Secrets and variables > Actions

  Secrets tab:
      SHEET_CSV_URL       the link from Step 1

  Variables tab:
      SITE_URL            https://creators.imperfectadulting.com
      CUSTOM_DOMAIN       creators.imperfectadulting.com
      SITE_TITLE          the directory's name, for example
                          UNMUTED Creator Directory
      SITE_DESCRIPTION    one or two sentences shown under the title
      GA_MEASUREMENT_ID   your Google Analytics ID (starts with G-)

  SITE_TITLE and SITE_DESCRIPTION are optional. If you rename the brand
  later, just change these two variables and run the workflow.

STEP 4. Turn on publishing
  Settings > Pages > Source: GitHub Actions.
  Custom domain: creators.imperfectadulting.com > Save.

STEP 5. Point the subdomain
  In imperfectadulting.com's DNS (where you added the guests record), add a CNAME:
      Name:  creators
      Value: amysaysso.github.io
  When the DNS check passes, tick "Enforce HTTPS".

STEP 6. Run it
  Actions tab > "Build and publish creator directory" > Run workflow
  (the button above the list of runs, not "Re-run" on an old run).


AFTER LAUNCH
------------
- Submit https://creators.imperfectadulting.com/sitemap.xml in Search Console.
  It goes in the same imperfectadulting.com Domain property as the guest
  directory's sitemap.
- Point the old directory page and menu link to the new address.
- If you move to a brand domain later: change SITE_URL and CUSTOM_DOMAIN,
  add the new domain's DNS record, and redirect the old address.
- To link to one show: https://creators.imperfectadulting.com/#show-name
  (the show name in lowercase with dashes).
