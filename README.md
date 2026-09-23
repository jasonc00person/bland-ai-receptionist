# AI Receptionist for Bland (copy, paste, call)

A phone receptionist that answers your business line, books the appointment, takes down what the customer needs, texts them a confirmation, and hangs up on its own. It is funny, it handles rude callers, and it tells the truth when someone asks "am I talking to an AI?"

Built on [Bland](https://app.bland.ai). The example is a car shop, but it is a template: swap the name, the hours, and the questions and it works for any appointment business.

**Video walkthrough:** _coming soon_

## What the call sounds like

1. Picks up: "Apex Auto Works, this is Clint. What's up?"
2. Offers the open times and locks one in.
3. Gets their name and the year, make and model.
4. Asks what the car needs. The caller can dump six things in one breath and it keeps all of them, then reads the list back.
5. Texts the caller mid-call: "You're booked for next Tuesday at 9:00 AM. Text us back your VIN and a link to the part you bought."
6. Asks if there's anything else, says goodbye, and hangs up.

At any point, if the caller asks whether they're talking to an AI (politely or not), it says yes, offers a real person, and picks the booking back up where it left off.

## What you need

- A Bland account with a phone number. Sign up at [app.bland.ai](https://app.bland.ai). The Agent Phone Plan gives you a number with unlimited US and Canada minutes and texts.
- Your Bland API key (in the Bland dashboard under Settings, API Keys).
- Python 3. Macs already have it. On Windows, install it from [python.org](https://www.python.org/downloads/) (tick "Add Python to PATH") and type `python` wherever this page says `python3`.
- About 10 minutes.

## Setup

Open Terminal (on a Mac: press Cmd+Space, type Terminal, press Enter) and paste these one at a time.

If your Mac ever pops up a box asking to install developer tools, click Install, wait for it to finish, then run the command again.

### 1. Get the files

```bash
git clone https://github.com/jasonc00person/bland-ai-receptionist.git
```

```bash
cd bland-ai-receptionist
```

No git? Click the green **Code** button on GitHub, choose **Download ZIP**, unzip it, then in Terminal type `cd ` (with a space) and drag the unzipped folder into the window before pressing Enter.

### 2. Run the installer

```bash
python3 scripts/setup.py
```

It walks you through everything:

1. Asks for your Bland API key. Nothing shows while you paste it, that's normal. It is saved in a hidden `.env` file on your computer and never uploaded to GitHub.
2. Asks for your business name, the receptionist's first name, and a real person's number for callers who want a human. It finds your Bland phone number on its own.
3. Builds the whole call flow inside your Bland account.
4. Runs a pretend call in text so you can see it book, text, and hang up. The test text goes to your own Bland number, not to a customer.
5. Asks before connecting your Bland number to the receptionist.

Then call your number from your cell. You should get one text, and it should hang up by itself at the end.

### Test it again any time

```bash
python3 scripts/simulate.py
```

Two more test callers are included:

```bash
python3 scripts/simulate.py tests/rude_caller.json
```

```bash
python3 scripts/simulate.py tests/service_first.json
```

If you skipped connecting your number during setup:

```bash
python3 scripts/setup.py --attach
```

### Your settings

Your answers are saved in `config.json`. Open it in any text editor to change them, then apply the changes:

```bash
python3 scripts/setup.py --update --attach
```

| Setting | What it is |
| --- | --- |
| `shop_name` | Your business name, exactly how it should be said on the phone |
| `agent_name` | The receptionist's first name |
| `phone_number` | Your Bland phone number, like `+15551234567` |
| `transfer_number` | A real person's number, for callers who ask for a human |
| `voice_id` | Optional. A voice ID from the Voices page in Bland. Leave empty for the default. |

## Make it yours

Everything the receptionist says lives in plain text files in the `prompts/` folder. One file per step of the call.

- **Hours, personality, humor, house rules:** `prompts/_global.md`. The CONFIG block at the top holds the open days and times.
- **Each step of the call:** `prompts/<Step Name>.md` is what it does in that step. `prompts/<Step Name>.exit.md` is what has to be true before it moves on.
- **The text message:** search `pathway.json` for `agent_message` and edit the sentence.

After editing, push your changes to Bland:

```bash
python3 scripts/setup.py --update
```

Then run the test calls again. `--update` overwrites anything you changed by hand in the Bland editor, so pick one place to edit: these files, or the editor.

**Easiest way to customize:** open this folder in [Claude Code](https://claude.com/claude-code) and say what you want in plain English, like "change this to a dental office that books cleanings Monday through Thursday, then update and test it." The included `CLAUDE.md` tells Claude how this project works.

## Things we learned the hard way

These are baked into the template already. Keep them in mind if you change the flow.

- **Never let the caller talk while the flow is sitting on the text-message step.** Bland re-sends the text every time that step is re-entered. Our first live test sent 10 identical texts. The fix: the text step routes instantly to the next step based on the response code, with no caller turn.
- **Steps should wait on what the caller said, never on what the agent has to say.** "Repeat the time back before moving on" makes a step hold an extra turn and swallow the rest of the call.
- **Keep the flow in one line.** Shortcuts like "skip to the work list if they mention it first" let callers skip the step that saves the appointment time, and the text goes out with blanks in it.
- **The "are you an AI?" trigger has to be strict.** Loose wording makes it fire on "thanks" and "bye."
- **Write prompts the way people talk.** Stiff example lines get repeated word for word. Loose ones with an "uh" and a false start sound human.
- **Test three times after any change.** One passing test proves nothing. Looser, funnier prompts make routing less predictable.

## Files

```
pathway.json          The complete call flow (steps, routing, text message)
prompts/              Every prompt as an editable text file
scripts/setup.py      Installs, attaches, or updates the flow in your Bland account
scripts/simulate.py   Text-only test calls
scripts/prompts.py    Syncs prompts/ with pathway.json
tests/                Three scripted callers
config.example.json   Starting point for config.json (setup.py fills it in)
.env.example          Starting point for .env, where your API key lives
CLAUDE.md             Instructions for Claude Code
```

## Safety notes

- Your API key lives in `.env` on your machine and inside your own Bland pathway (the text step needs it to send texts from your number). It is never in this repo. Do not commit `.env` or `config.json`.
- Tell callers the truth. This template always admits it is an AI when asked and always offers a human. Keep it that way, and check your local rules on call recording and AI disclosure.
- The "calendar link" line at the end is only spoken. No calendar is connected. Hook one up with a second webhook step, or remove the line in `prompts/Confirm And End.md`.

## License

MIT. Use it, change it, sell work built on it.

---

Built by Jason Cooperson. Want to learn how to build things like this with AI? [Join the AI Leverage Lab](https://www.skool.com/leveragelab).
