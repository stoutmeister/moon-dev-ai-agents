# ai agents 

## build list 
[] solana copy trading agent 
    [x] get the copy bot live again
    [x] update the call to be from api.moondev.com to save a ton of time and be able to execute copy bot way way faster. 
    [x] build out agent in order to view that api call 
    [x] build out a DB of recent TXs for any tracked wallet we have or that has been put in the discord and constantly run then give access to everyone 
    [] have the scanned transaction tokens shown on a discord channel, with the api key and link + tutorial so everyone can access it
[x] sentiment agent 
[x] rbi agent 
[] solana sniper agent
    - Remember this year I am trying to replicate what I've done in the last four years with AI agents so I've had a lot of success with the Solana Sniper and the Copy Trading Agent as a somewhat of a scanner of new tokens on the market and new narratives that are bubbling up. So for the copy bot agent and also this sniper agent. I think I want to run the sniper and the copy bot and then let the agent look at that filter data opposed to just sending in all of the data to the agent, the LLMs that will get too messy, in my opinion. 
[x] liquidation trading agent
[x] open interest trading  agent
[x] funding rate trading agent 
[x] coin gecko agent - if i give a agent or swarm access to all of coingecko data from 2014, it will be able to cook no doubt.
    - i want these agents to look for high volume tokens that are not on major exchanges

[x] listing arb agent - idea is to find freakishly high volume tokens that keep it up for a few days, or weeks that are not on binance or cb. 
    - current problem is that its a fuck ton of data i need to go through, like 15,000 tokens on coingecko 
    - i have birdeye and coin gecko, i can set up scanners that are looking for high volume tokens, no worries, its just time and api cost. 

    - possibly look thorugh recently added coins, they are fresh on coingecko 

[] coin gecko agent ehancements, its a vast api so i wanna look thorugh it and come up with ideas
    - top gainers and losers could be cool to work off as a scanner: https://docs.coingecko.com/reference/coins-top-gainers-losers
    - see every morning the recently added coins https://docs.coingecko.com/reference/coins-list-new
[] build a flow to run these agents every 24 hours, like the new or top agent, the listing arb agent etc. 

## 🏠 Real Estate Wholesaling: Skip Tracer + Dialer

Two agents that form a lead-to-call pipeline for wholesaling real estate:

`leads.csv → skip_tracer_agent.py → traced_leads.csv → wholesale_dialer_agent.py → call_log.csv`

**`skip_tracer_agent.py`** — takes a CSV of property addresses/owner names, pulls
owner phone numbers + emails from a skip trace API (BatchData), scrubs against
your local `dnc_list.csv`, and uses AI to score seller motivation so the hottest
leads get called first.
- Needs `BATCHDATA_API_KEY` in `.env` (+ `ANTHROPIC_KEY` if AI scoring is on)
- Run once with no `leads.csv` and it drops a fill-in template for you
- Output sorted by motivation score → `src/data/skip_tracer/traced_leads.csv`

**`wholesale_dialer_agent.py`** — works the traced queue with an AI acquisitions
rep that qualifies the deal (condition, price, timeline, motivation) and captures
a disposition per call. Opt-outs are written to a shared `dnc_list.csv` the
tracer scrubs against, so you never call them again.
- `TESTING_MODE = True` → practice in your terminal (AI is the rep, you type the
  seller). No Twilio needed.
- `TESTING_MODE = False` → live outbound calls via Twilio (`TWILIO_*` in `.env`)
- Enforces TCPA calling hours (9am–8pm by default) and a motivation floor

⚠️ **Compliance is on you**: follow the TCPA, scrub the national DNC registry,
respect calling hours, and identify yourself. The local `dnc_list.csv` scrub and
calling-hour guard are guardrails, not a substitute for a real DNC registry scrub.

```bash
python src/agents/skip_tracer_agent.py      # trace leads → build queue
python src/agents/wholesale_dialer_agent.py # work the queue
```

## Need an API key? for a limited time, bootcamp members get free api keys for claude, openai, helius, birdeye & quant elite gets access to the moon dev api. join here: https://algotradecamp.com


