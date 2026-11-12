# Case routing results viewer

Serve the repository root with `python3 -m http.server 8000`, then open `http://localhost:8000/ui/`.
Use `http://localhost:8000/ui/?data=sample` to view the included sample. The default dataset is `../data/starter`.

The viewer is read-only and uses plain JavaScript and CSS. It fetches:

- `json/ticket.json`
- `json/assignment_event.json`
- `json/sla_event.json`
- `json/message.json`
- `json/agent.json`
- `metrics.json`
- `ground_truth/ground_truth.json`
- `validation/findings.json`

The selected data folder must be relative to `ui/` or an absolute URL served by the same origin.
