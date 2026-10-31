# WRT-EDIT-02B review app

> **Closed pilot.** The manual 50-passage exercise stopped after 10 passages.
> This page is preserved as historical evidence, not for completion or
> threshold tuning. Use Workbench’s native **Editing** stage for editorial
> decisions.

Open `WRT-EDIT-02B-review.html` in a browser.

- The page starts with **Set 1 of 5**: 10 passages.
- Score each passage with the buttons, then click **Next**.
- At the end of the set you can download a CSV and stop, or continue to the
  next set.
- The CSV always has 50 rows in the original `P01`–`P50` order. Unscored rows
  are blank, so a 10-passage review produces a valid partial CSV.
- Answers are saved in this browser's local storage. Download the CSV before
  clearing browser data or switching machines.
- The page contains no book names, diagnostic categories, Writer scores or
  findings. It makes no network requests.
- The reviewer field is prefilled as **AI-assisted reviewer (prior diagnostic
  exposure)**. Change it if needed.

The page is a convenience wrapper around the frozen blind packet. The canonical
packet remains `calibration-blind-passages.csv` and
`calibration-review-template.csv` in `../review-packet/`.
