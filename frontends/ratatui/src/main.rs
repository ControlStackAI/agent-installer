use crossterm::{
    event::{
        self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind, KeyModifiers,
        MouseButton, MouseEventKind,
    },
    execute,
};
use ratatui::{
    Frame, Terminal,
    backend::TestBackend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span, Text},
    widgets::{Block, BorderType, Borders, Clear, List, ListItem, ListState, Paragraph, Wrap},
};
use serde_json::{Value, json};
use std::{
    env,
    io::{self, IsTerminal},
    process::{Command, Stdio},
    sync::mpsc::{self, Receiver},
    thread,
    time::Duration,
};

const BG: Color = Color::Rgb(9, 18, 32);
const PANEL: Color = Color::Rgb(15, 29, 47);
const BORDER: Color = Color::Rgb(43, 65, 88);
const TEXT: Color = Color::Rgb(226, 236, 247);
const MUTED: Color = Color::Rgb(147, 168, 191);
const ACCENT: Color = Color::Rgb(132, 192, 255);
const GREEN: Color = Color::Rgb(112, 216, 187);
const AMBER: Color = Color::Rgb(245, 192, 119);
const VIEWS: [&str; 8] = [
    "Overview",
    "Desktop presets",
    "Your choices",
    "Hardware",
    "Plan review",
    "Reboot handoff",
    "Recovery",
    "Checks",
];

#[derive(Clone)]
struct Backend {
    python: String,
    share: String,
}
impl Backend {
    fn command(&self, args: &[String]) -> Command {
        let mut command = Command::new(&self.python);
        command
            .args(["-m", "core.frontend", "--share", &self.share])
            .args(args);
        command
    }
    fn request(&self, args: Vec<String>) -> Receiver<Result<Value, String>> {
        let backend = self.clone();
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            let result = (|| {
                let output = backend
                    .command(&args)
                    .stdin(Stdio::null())
                    .output()
                    .map_err(|_| "Could not start the shared installer tools.".to_string())?;
                let response: Value = serde_json::from_slice(&output.stdout).map_err(|_| "The shared tools returned an unreadable response. Open the troubleshooting shell for details.".to_string())?;
                if response["ok"] == true {
                    Ok(response["data"].clone())
                } else {
                    Err(response["error"]
                        .as_str()
                        .unwrap_or("The request could not finish.")
                        .to_string())
                }
            })();
            let _ = tx.send(result);
        });
        rx
    }
}

#[derive(Clone, Copy, PartialEq, Debug)]
enum Page {
    Welcome,
    View(usize),
    Help,
}
#[derive(Clone)]
enum Prompt {
    Import,
    Export,
    ConfirmExport(String, String),
    ConfirmPreset(String),
}
struct App {
    page: Page,
    welcome: usize,
    preset: usize,
    scroll: u16,
    tick: usize,
    data: Value,
    detail: String,
    message: String,
    prompt: Option<Prompt>,
    input: String,
    job: Option<(Receiver<Result<Value, String>>, String)>,
    backend: Backend,
    preview: bool,
    console_palette: bool,
}

fn preview_data() -> Value {
    json!({"distro":"Arch Linux", "kernel":"7.2 · example preview", "phase":"live", "presets":[
        {"id":"familiar","name":"Familiar desktop","description":"Plasma: an application menu, taskbar and graphical settings. A comfortable starting point.","defaults":{"desktop":"plasma","filesystem":"zfs"}},
        {"id":"simple","name":"Simple desktop","description":"GNOME: a focused workspace with fewer visible controls.","defaults":{"desktop":"gnome","filesystem":"zfs"}},
        {"id":"hyprland","name":"Hyprland with Quickshell","description":"Three floating islands and a searchable application launcher with icons.","defaults":{"desktop":"hyprland-quickshell","filesystem":"zfs"}},
        {"id":"minimal","name":"Minimal or server","description":"A command-line system. Add only the applications and services you need.","defaults":{"desktop":"none","filesystem":"zfs"}},
        {"id":"custom","name":"Your own setup","description":"Start with a blank canvas. Every option is yours to choose.","defaults":{}}
    ],"handoff":null,"review":"No disk selected. Your assistant will prepare a plan for you to review.","fingerprint":"preview", "readiness":{"ready":false,"checks":[]}})
}
impl App {
    fn new(backend: Backend, preview: bool) -> Self {
        Self {
            page: Page::Welcome,
            welcome: 0,
            preset: 0,
            scroll: 0,
            tick: 0,
            data: if preview { preview_data() } else { json!({}) },
            detail: String::new(),
            message: "Choose how you would like to begin.".into(),
            prompt: None,
            input: String::new(),
            job: None,
            backend,
            preview,
            console_palette: env::var("TERM").as_deref() == Ok("linux"),
        }
    }
    fn request(&mut self, action: &str, args: &[String]) {
        if self.job.is_some() {
            self.message =
                "A check is still running. You can browse other pages while it finishes.".into();
            return;
        }
        self.scroll = 0;
        if self.preview {
            self.message = "Design preview: no system commands, account sign-in or file changes are performed.".into();
            if action == "preset" {
                if let Some(entry) = self.data["presets"]
                    .as_array()
                    .and_then(|p| p.iter().find(|p| p["id"] == args[0]))
                    .cloned()
                {
                    self.data["handoff"] = json!({"preset":entry["id"],"choices":entry["defaults"],"intent":"install", "completed":[], "remaining":["Discuss your choices with the assistant"], "notes":[]});
                }
            } else if action == "intent" {
                self.data["handoff"]["intent"] = json!(args[0]);
            }
            return;
        }
        self.message = match action { "preflight" => "Checking internet, clock and the live ZFS module. Time synchronization can take a moment.", "inventory" => "Inspecting hardware read-only. No disk changes are made.", "verify" => "Collecting boot evidence and remaining verification steps.", _ => "Working with your local setup record…" }.into();
        let mut command = vec![action.to_string()];
        command.extend_from_slice(args);
        self.job = Some((self.backend.request(command), action.to_string()));
    }
    fn poll(&mut self) {
        let result = self
            .job
            .as_ref()
            .and_then(|(rx, action)| rx.try_recv().ok().map(|r| (r, action.clone())));
        if let Some((result, action)) = result {
            self.job = None;
            match result {
                Ok(data) => {
                    if data.get("presets").is_some() {
                        self.data = data;
                    } else if let Some(message) = data["message"].as_str() {
                        self.message = message.into();
                    } else {
                        self.detail = serde_json::to_string_pretty(&data).unwrap_or_default();
                    }
                    if action != "export" {
                        self.message = match action.as_str() { "preflight" if self.data["readiness"]["ready"] == true => "Ready to sign in. Checks run again before your assistant starts.", "preflight" => "A readiness check needs attention. Open network setup or ask for help.", "preset" => "Starting choices saved. Customize anything or talk to your assistant.", "import" => "Imported as historical context. The assistant will recheck this computer before continuing.", "inventory" => "Hardware evidence collected. Collection alone does not prove a device works.", "verify" => "Evidence collected. Review the manual checks before claiming a working installation.", _ => "Your local setup is ready." }.into();
                    }
                }
                Err(error) => {
                    self.message = error;
                }
            }
        }
    }
    fn set_page(&mut self, index: usize) {
        self.page = Page::View(index % VIEWS.len());
        self.scroll = 0;
        self.detail.clear();
    }
    fn apply_preset(&mut self) {
        let id = self.data["presets"]
            .as_array()
            .and_then(|p| p.get(self.preset))
            .and_then(|p| p["id"].as_str())
            .map(str::to_string);
        if let Some(id) = id {
            if self.data["handoff"].is_object() {
                self.prompt = Some(Prompt::ConfirmPreset(id));
            } else {
                self.request("preset", &[id]);
            }
        }
    }
    fn prompt_input(&mut self, prompt: Prompt) {
        self.prompt = Some(prompt);
        self.input.clear();
    }
}

fn block(title: &str) -> Block<'_> {
    Block::default()
        .title(Line::from(vec![
            Span::raw(" "),
            Span::styled(title, Style::default().fg(ACCENT)),
            Span::raw(" "),
        ]))
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(BORDER))
        .style(Style::default().bg(PANEL).fg(TEXT))
}
fn paragraph<'a>(text: impl Into<Text<'a>>, title: &'a str, scroll: u16) -> Paragraph<'a> {
    Paragraph::new(text)
        .block(block(title))
        .wrap(Wrap { trim: false })
        .scroll((scroll, 0))
}
fn body_layout(area: Rect) -> [Rect; 3] {
    let parts = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(4),
            Constraint::Length(3),
        ])
        .margin(if area.width >= 80 && area.height >= 30 {
            2
        } else {
            1
        })
        .split(area);
    [parts[0], parts[1], parts[2]]
}
fn card(frame: &mut Frame, area: Rect, title: &str, text: &str, selected: bool) {
    let border = if selected { ACCENT } else { BORDER };
    frame.render_widget(
        Paragraph::new(text)
            .wrap(Wrap { trim: false })
            .block(block(title).border_style(Style::default().fg(border)))
            .style(
                Style::default()
                    .fg(if selected { TEXT } else { MUTED })
                    .bg(if selected {
                        Color::Rgb(22, 43, 66)
                    } else {
                        PANEL
                    }),
            ),
        area,
    );
}
fn page_text(app: &App, view: usize) -> String {
    let record = &app.data["handoff"];
    match view {
        0 => {
            let selected = record["preset"].as_str().unwrap_or("Not chosen — your assistant can recommend one");
            let mut text = format!("YOUR NEXT STEP\n\nChoose a starting desktop, or tell the assistant what you want.\nYou can change every choice. No Linux commands are required.\n\nStarting point   {selected}\n\nREADINESS\n");
            if let Some(checks) = app.data["readiness"]["checks"].as_array().filter(|v| !v.is_empty()) {
                for check in checks { text.push_str(&format!("\n{}  {}\n   {}\n", if check["status"] == "pass" { "PASS" } else { "CHECK" }, check["name"].as_str().unwrap_or("Check"), check["detail"].as_str().unwrap_or(""))); }
            } else { text.push_str("\nNot checked yet. Press R to check internet, time and live ZFS.\n"); }
            text.push_str("\nA  Talk to your assistant     N  Set up a network\n\nYour assistant explains the disk plan and asks before erasure.\nThis live environment provides agent-directed installation.\n"); text
        },
        2 => format!("YOUR SETUP, YOUR CHOICES\n\nPresets are starting points. Customize the desktop, applications,\nservices, storage, key bindings, appearance or accessibility.\n\nA  Describe your changes to the assistant\nE  Edit the complete non-secret setup record (advanced)\n\n{}", if record.is_object() { serde_json::to_string_pretty(&record["choices"]).unwrap_or_default() } else { "No choices yet. Choose a preset, or start a conversation.".into() }),
        3 => if app.detail.is_empty() { "HARDWARE READINESS\n\nPress Enter to collect a read-only hardware report.\nThe assistant can inspect drivers, firmware needs, disks,\nnetworking, radio blocks, memory and available space.\n\nMissing tools and untested devices remain visible.\nThe report does not qualify an installation or repair anything.\n\nA  Ask the assistant to investigate a problem".into() } else { app.detail.clone() },
        4 => format!("REVIEW BEFORE CHANGES\n\nYour assistant prepares this plan and explains what will change.\nThis screen records no permission to erase disks.\nA  Discuss or revise the plan     E  Edit the record (advanced)\n\n{}", app.data["review"].as_str().unwrap_or("No plan yet. Start with a preset or conversation.")),
        5 => format!("CONTINUE AFTER REBOOT\n\nI  Import a saved record      S  Save this reviewed record\nA  Ask the assistant to arrange continuation\n\nOnly this non-secret JSON record is saved. Review every field\nbefore saving. Sign-in, credentials and transcripts stay out.\nSaving a record does not install or automatically start an agent.\n\n{}", if record.is_object() { serde_json::to_string_pretty(record).unwrap_or_default() } else { "No record yet. Choose a preset or ask the assistant to create one.".into() }),
        6 => "RECOVER THIS COMPUTER\n\nPress Enter to ask the assistant for recovery help.\nIt starts with read-only inspection and explains its findings.\n\nIt can help plan boot repair, file recovery and ZFS snapshot\nrestoration. Changes require a current, reviewed plan.\nNo pool import, rollback or boot repair runs from this menu.\n\nA  Talk to the assistant     N  Set up a network".into(),
        7 => if app.detail.is_empty() { "VERIFICATION\n\nPress Enter to collect current boot evidence and a checklist.\nA live USB or chroot cannot prove an installed system boots.\nAfter installing, boot without the USB and verify the actual\nroot, desktop, network, audio and recovery path.\n\nR  Check this live environment's internet, time and ZFS readiness\n\nEvidence collection is not an automatic installation-success claim.".into() } else { app.detail.clone() },
        _ => String::new(),
    }
}
fn render(frame: &mut Frame, app: &App) {
    let area = frame.area();
    frame.render_widget(
        Block::default().style(Style::default().bg(BG).fg(TEXT)),
        area,
    );
    let [head, body, footer] = body_layout(area);
    let badge = if app.preview {
        "DESIGN PREVIEW"
    } else {
        "LIVE SESSION"
    };
    let distro = app.data["distro"]
        .as_str()
        .unwrap_or("Detecting live environment");
    let kernel = app.data["kernel"].as_str().unwrap_or("");
    frame.render_widget(
        Paragraph::new(vec![
            Line::from(vec![
                Span::styled(
                    "CONTROLSTACK",
                    Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
                ),
                Span::styled("  /  AGENT INSTALLER", Style::default().fg(TEXT)),
                Span::styled(format!("    {badge}"), Style::default().fg(AMBER)),
            ]),
            Line::from(Span::styled(
                format!("{distro}   ·   {kernel}   ·   Your computer, your choices"),
                Style::default().fg(MUTED),
            )),
        ]),
        head,
    );
    if area.width < 55 || area.height < 18 {
        frame.render_widget(paragraph("This terminal is small. Enlarge it to at least 55 × 18 for the full interface.\n\nG  Guided setup\nD  Direct agent conversation\nQ  Leave setup", "Welcome", 0), body);
    } else if app.page == Page::Welcome {
        let horizontal = body.width >= 100;
        let welcome_width = body.width.min(116);
        let welcome_height = body.height.min(if horizontal { 18 } else { 20 });
        let welcome_area = Rect::new(
            body.x + (body.width - welcome_width) / 2,
            body.y + (body.height - welcome_height) / 2,
            welcome_width,
            welcome_height,
        );
        let parts = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(2),
                Constraint::Min(10),
                Constraint::Length(2),
            ])
            .split(welcome_area);
        frame.render_widget(Paragraph::new("Make yourself at home.\nChoose a little guidance, or go straight to a conversation.").style(Style::default().fg(TEXT)).wrap(Wrap{trim:false}),parts[0]);
        let cards = Layout::default()
            .direction(if horizontal {
                Direction::Horizontal
            } else {
                Direction::Vertical
            })
            .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
            .spacing(1)
            .split(parts[1]);
        card(
            frame,
            cards[0],
            "1  Guided setup",
            if horizontal {
                "A clear place to start.\n\nExplore desktops, check hardware, review your plan and continue saved work. Customize anything."
            } else {
                "Choose a desktop, check hardware and review your plan.\nCustomize every choice with your assistant."
            },
            app.welcome == 0,
        );
        card(
            frame,
            cards[1],
            "2  Direct agent conversation",
            if horizontal {
                "Tell your assistant what you want.\n\nA flexible path for your own configuration, a detailed request or hands-on troubleshooting."
            } else {
                "Describe exactly what you want to install or recover.\nKeep full control of your configuration."
            },
            app.welcome == 1,
        );
        frame.render_widget(
            Paragraph::new("Your assistant asks before erasing data. Sign-in stays in memory.")
                .style(Style::default().fg(MUTED))
                .wrap(Wrap { trim: false }),
            parts[2],
        );
    } else if app.page == Page::Help {
        frame.render_widget(paragraph("MAKE IT YOURS\n\nTab / Left / Right   Move between pages\n1–8                  Jump to a page\nUp / Down            Select a preset or scroll the page\nPage Up / Page Down  Scroll further\nEnter                Use the selected page's action\nA                    Talk to the assistant\nN                    Network setup (Wi-Fi or Ethernet)\nR                    Check internet, clock and live ZFS\nE                    Edit all non-secret choices (advanced)\nI / S                Import / save on the Reboot handoff page\nEsc                  Back or cancel\nQ                    Leave the interface\n\nNetwork setup, editing, sign-in and conversation use the full\nterminal, then return here. Secrets are never entered in a UI form.\nThe assistant rechecks readiness before login and launch.\n\nPresets never restrict advanced choices. Plan review is not\ndisk-erasure permission. Imported records are historical data.\n\nFor basic console access, run agent-installer --text.","Help & keyboard shortcuts",app.scroll),body);
    } else if let Page::View(view) = app.page {
        let wide = body.width >= 90;
        let regions = Layout::default()
            .direction(Direction::Horizontal)
            .constraints(if wide {
                vec![Constraint::Length(25), Constraint::Min(20)]
            } else {
                vec![Constraint::Length(0), Constraint::Min(20)]
            })
            .spacing(if wide { 2 } else { 0 })
            .split(body);
        if wide {
            let items: Vec<ListItem> = VIEWS
                .iter()
                .enumerate()
                .map(|(i, s)| ListItem::new(format!(" {}  {}", i + 1, s)))
                .collect();
            let mut state = ListState::default().with_selected(Some(view));
            frame.render_stateful_widget(
                List::new(items)
                    .block(block("Your installation"))
                    .highlight_style(
                        Style::default()
                            .bg(Color::Rgb(28, 53, 76))
                            .fg(ACCENT)
                            .add_modifier(Modifier::BOLD),
                    )
                    .highlight_symbol("›"),
                regions[0],
                &mut state,
            );
        }
        if view == 1 {
            let parts = Layout::default()
                .direction(Direction::Vertical)
                .constraints([
                    Constraint::Length(3),
                    Constraint::Min(5),
                    Constraint::Length(6),
                ])
                .split(regions[1]);
            frame.render_widget(Paragraph::new("Choose a starting point. Change every option later.\nUp/Down selects · Enter applies · A asks for a recommendation").style(Style::default().fg(MUTED)).wrap(Wrap{trim:false}),parts[0]);
            let entries = app.data["presets"].as_array().cloned().unwrap_or_default();
            let items: Vec<ListItem> = entries
                .iter()
                .map(|e| {
                    ListItem::new(Line::from(Span::styled(
                        format!("  {}", e["name"].as_str().unwrap_or("Preset")),
                        Style::default().fg(TEXT),
                    )))
                })
                .collect();
            let mut state = ListState::default().with_selected(Some(app.preset));
            frame.render_stateful_widget(
                List::new(items)
                    .block(block("Desktop presets"))
                    .highlight_style(
                        Style::default()
                            .bg(Color::Rgb(28, 53, 76))
                            .fg(GREEN)
                            .add_modifier(Modifier::BOLD),
                    )
                    .highlight_symbol("›"),
                parts[1],
                &mut state,
            );
            let description = entries
                .get(app.preset)
                .and_then(|e| e["description"].as_str())
                .unwrap_or("Loading public presets…");
            frame.render_widget(
                paragraph(
                    format!("{}\n\nAgent-built; every option is editable.", description),
                    "About this starting point",
                    0,
                ),
                parts[2],
            );
        } else {
            frame.render_widget(
                paragraph(page_text(app, view), VIEWS[view], app.scroll),
                regions[1],
            );
        }
    }
    let spin = ["◐", "◓", "◑", "◒"][app.tick % 4];
    let status = if app.job.is_some() {
        format!("{spin}  {}", app.message)
    } else {
        app.message.clone()
    };
    let shortcuts = if app.page == Page::Welcome {
        "↑↓ Select   Enter Continue   G Guided   D Direct   F1 Help   Q Leave"
    } else {
        "Tab Pages   ↑↓ Scroll   A Assistant   N Network   R Ready   F1 Help   Esc Back"
    };
    frame.render_widget(
        Paragraph::new(vec![
            Line::from(Span::styled(
                status,
                Style::default().fg(if app.job.is_some() { GREEN } else { MUTED }),
            )),
            Line::from(Span::styled(shortcuts, Style::default().fg(ACCENT))),
        ])
        .wrap(Wrap { trim: false }),
        footer,
    );
    if let Some(prompt) = &app.prompt {
        let width = area.width.saturating_sub(4).min(78);
        let height = area.height.saturating_sub(2).min(12);
        let rect = Rect::new(
            (area.width - width) / 2,
            (area.height - height) / 2,
            width,
            height,
        );
        frame.render_widget(Clear, rect);
        let (title,text)=match prompt {
            Prompt::Import => ("Import historical context",format!("Path to one non-secret handoff JSON file:\n\n{}▏\n\nEnter imports as historical data. It does not approve disk changes.\nEsc cancels; previous local work is kept in a backup.",app.input)),
            Prompt::Export => ("Save reviewed continuation",format!("Review the full JSON on the Reboot handoff page first.\nPath to a new file on your approved persistent destination:\n\n{}▏\n\nEnter previews the save confirmation. Esc cancels.\nNo credentials or conversation history are exported.",app.input)),
            Prompt::ConfirmExport(path,_) => ("Confirm this save",format!("Save the reviewed non-secret JSON record to:\n\n{path}\n\nThis is permission to save this file only.\nIt is not disk-erasure approval or an automatic agent install.\n\nY  Save this record       Esc / N  Cancel")),
            Prompt::ConfirmPreset(_) => ("Replace starting choices?","This replaces the current starting choices. Your plan and notes\nare kept for review, and old checks are marked pending.\nA backup of your previous record stays in this RAM session.\n\nY  Replace choices       Esc / N  Keep current choices".into()),
        };
        frame.render_widget(paragraph(text, title, 0), rect);
    }
    if app.console_palette {
        // Linux virtual consoles understand sixteen colors, not RGB escapes.
        // Translate the complete frame so labels and selected cards stay legible.
        for cell in &mut frame.buffer_mut().content {
            let style = cell.style();
            cell.set_style(style.fg(console_color(cell.fg)).bg(console_color(cell.bg)));
        }
    }
}

fn console_color(color: Color) -> Color {
    match color {
        BG | PANEL => Color::Black,
        BORDER => Color::Cyan,
        TEXT => Color::White,
        MUTED => Color::Gray,
        ACCENT => Color::LightCyan,
        GREEN => Color::LightGreen,
        AMBER => Color::LightYellow,
        Color::Rgb(22, 43, 66) | Color::Rgb(28, 53, 76) => Color::Blue,
        other => other,
    }
}

fn child(app: &mut App, terminal: &mut ratatui::DefaultTerminal, action: &str) -> io::Result<()> {
    if app.preview {
        app.message = "Design preview: this action is available on the live ISO.".into();
        return Ok(());
    }
    if app.job.is_some() {
        app.message = "Wait for the current check before opening an interactive tool.".into();
        return Ok(());
    }
    ratatui::restore();
    execute!(io::stdout(), DisableMouseCapture)?;
    let status = if action == "edit" {
        app.backend.command(&["edit".into()]).status()
    } else {
        let mut command = Command::new(&app.backend.python);
        command.args(["-m", "core.launcher"]);
        match action {
            "network" => {
                command.arg("--network");
            }
            "agent" => {
                command.args(["--direct", "--return-to-ui"]);
            }
            _ => {}
        }
        command.status()
    };
    *terminal = ratatui::init();
    execute!(io::stdout(), EnableMouseCapture)?;
    terminal.clear()?;
    app.message=match status {Ok(s) if s.success()=>"Back in setup. Your local choices are preserved.".into(),_=>"The interactive tool did not finish. You can retry, check networking or use the text interface.".into()};
    app.request("state", &[]);
    Ok(())
}
fn handle_prompt(app: &mut App, code: KeyCode) {
    let Some(prompt) = app.prompt.clone() else {
        return;
    };
    match code {
        KeyCode::Esc => app.prompt = None,
        KeyCode::Char('n' | 'N')
            if matches!(
                prompt,
                Prompt::ConfirmExport(..) | Prompt::ConfirmPreset(..)
            ) =>
        {
            app.prompt = None
        }
        KeyCode::Char('y' | 'Y')
            if matches!(
                prompt,
                Prompt::ConfirmExport(..) | Prompt::ConfirmPreset(..)
            ) =>
        {
            app.prompt = None;
            match prompt {
                Prompt::ConfirmExport(path, hash) => {
                    app.request("export", &[path, "--fingerprint".into(), hash])
                }
                Prompt::ConfirmPreset(id) => app.request("preset", &[id]),
                _ => {}
            }
        }
        KeyCode::Enter => match prompt {
            Prompt::Import if !app.input.trim().is_empty() => {
                let path = app.input.trim().to_string();
                app.prompt = None;
                app.request("import", &[path]);
            }
            Prompt::Export if !app.input.trim().is_empty() => {
                if app.data["handoff"].is_object() {
                    app.prompt = Some(Prompt::ConfirmExport(
                        app.input.trim().to_string(),
                        app.data["fingerprint"].as_str().unwrap_or("").into(),
                    ));
                } else {
                    app.message = "Create a setup record before saving it.".into();
                    app.prompt = None;
                }
            }
            _ => {}
        },
        KeyCode::Backspace => {
            app.input.pop();
        }
        KeyCode::Char(c)
            if matches!(prompt, Prompt::Import | Prompt::Export)
                && !c.is_control()
                && app.input.len() < 4096 =>
        {
            app.input.push(c)
        }
        _ => {}
    }
}
fn event_loop(terminal: &mut ratatui::DefaultTerminal, app: &mut App) -> io::Result<()> {
    if !app.preview {
        app.request("state", &[]);
    }
    loop {
        app.poll();
        terminal.draw(|f| render(f, app))?;
        app.tick = app.tick.wrapping_add(1);
        if !event::poll(Duration::from_millis(120))? {
            continue;
        }
        match event::read()? {
            Event::Key(key) if key.kind == KeyEventKind::Press => {
                if key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c') {
                    return Ok(());
                }
                if app.prompt.is_some() {
                    handle_prompt(app, key.code);
                    continue;
                }
                let code = match key.code {
                    KeyCode::Char(c) => KeyCode::Char(c.to_ascii_lowercase()),
                    other => other,
                };
                match code {
                    KeyCode::Char('q') => return Ok(()),
                    KeyCode::F(1) | KeyCode::Char('?') => {
                        app.page = Page::Help;
                        app.scroll = 0;
                    }
                    KeyCode::Esc => {
                        app.page = Page::Welcome;
                        app.scroll = 0;
                    }
                    KeyCode::Char('g') if app.page == Page::Welcome => app.set_page(0),
                    KeyCode::Char('d') if app.page == Page::Welcome => {
                        child(app, terminal, "agent")?
                    }
                    KeyCode::Char('a') => child(app, terminal, "agent")?,
                    KeyCode::Char('n') => child(app, terminal, "network")?,
                    KeyCode::Char('r') => app.request("preflight", &[]),
                    KeyCode::Char('e') if app.page != Page::Welcome => {
                        child(app, terminal, "edit")?
                    }
                    KeyCode::Char('i') if app.page == Page::View(5) => {
                        app.prompt_input(Prompt::Import)
                    }
                    KeyCode::Char('s') if app.page == Page::View(5) => {
                        app.prompt_input(Prompt::Export)
                    }
                    KeyCode::Char(c @ '1'..='8') if app.page != Page::Welcome => {
                        app.set_page(c as usize - '1' as usize)
                    }
                    KeyCode::Char('1') if app.page == Page::Welcome => app.set_page(0),
                    KeyCode::Char('2') if app.page == Page::Welcome => {
                        child(app, terminal, "agent")?
                    }
                    KeyCode::Tab | KeyCode::Right => match app.page {
                        Page::Welcome => app.welcome = 1 - app.welcome,
                        Page::View(i) => app.set_page(i + 1),
                        _ => {}
                    },
                    KeyCode::BackTab | KeyCode::Left => match app.page {
                        Page::Welcome => app.welcome = 1 - app.welcome,
                        Page::View(i) => app.set_page((i + VIEWS.len() - 1) % VIEWS.len()),
                        _ => {}
                    },
                    KeyCode::Down => match app.page {
                        Page::Welcome => app.welcome = 1,
                        Page::View(1) => {
                            let count = app.data["presets"].as_array().map_or(0, Vec::len);
                            app.preset = (app.preset + 1).min(count.saturating_sub(1));
                        }
                        _ => app.scroll = app.scroll.saturating_add(1),
                    },
                    KeyCode::Up => match app.page {
                        Page::Welcome => app.welcome = 0,
                        Page::View(1) => app.preset = app.preset.saturating_sub(1),
                        _ => app.scroll = app.scroll.saturating_sub(1),
                    },
                    KeyCode::PageDown => app.scroll = app.scroll.saturating_add(8),
                    KeyCode::PageUp => app.scroll = app.scroll.saturating_sub(8),
                    KeyCode::Enter => match app.page {
                        Page::Welcome if app.welcome == 0 => app.set_page(0),
                        Page::Welcome => child(app, terminal, "agent")?,
                        Page::View(1) => app.apply_preset(),
                        Page::View(3) => app.request("inventory", &[]),
                        Page::View(6) => {
                            app.request("intent", &["recover".into()]);
                            app.message="Recovery selected. Press A after the record is ready to talk to the assistant.".into();
                        }
                        Page::View(7) => app.request("verify", &[]),
                        _ => {}
                    },
                    _ => {}
                }
            }
            Event::Mouse(mouse)
                if mouse.kind == MouseEventKind::Down(MouseButton::Left)
                    && app.prompt.is_none() =>
            {
                let size = terminal.size()?;
                let area = Rect::new(0, 0, size.width, size.height);
                let body = body_layout(area)[1];
                if let Page::View(_) = app.page {
                    if body.width >= 90
                        && mouse.column >= body.x
                        && mouse.column < body.x + 25
                        && mouse.row > body.y
                        && mouse.row < body.y + 9
                    {
                        app.set_page((mouse.row - body.y - 1) as usize);
                    }
                }
            }
            _ => {}
        }
    }
}
fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|a| a == "--version") {
        println!("agent-installer-tui 0.1.0 (Ratatui 0.30.2)");
        return Ok(());
    }
    if args.iter().any(|a| a == "--help") {
        println!(
            "agent-installer-tui [--preview] [--render WIDTH HEIGHT] [--screen welcome|overview|presets|review] [--python PATH] [--share PATH]\nUse agent-installer on the live ISO. Preview and render never invoke system actions."
        );
        return Ok(());
    }
    let option = |name: &str, default: &str| {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .cloned()
            .unwrap_or_else(|| default.into())
    };
    let render_at = args.iter().position(|a| a == "--render");
    let preview = render_at.is_some() || args.iter().any(|a| a == "--preview");
    let backend = Backend {
        python: option("--python", "python3"),
        share: option("--share", "/usr/share/agent-installer"),
    };
    let mut app = App::new(backend, preview);
    match option("--screen", "welcome").as_str() {
        "overview" => app.page = Page::View(0),
        "presets" => app.page = Page::View(1),
        "review" => app.page = Page::View(4),
        _ => {}
    }
    if let Some(i) = render_at {
        let width = args
            .get(i + 1)
            .and_then(|s| s.parse::<u16>().ok())
            .unwrap_or(100)
            .clamp(20, 240);
        let height = args
            .get(i + 2)
            .and_then(|s| s.parse::<u16>().ok())
            .unwrap_or(32)
            .clamp(10, 100);
        let mut terminal = Terminal::new(TestBackend::new(width, height)).unwrap();
        terminal.draw(|f| render(f, &app)).unwrap();
        let buffer = terminal.backend().buffer();
        for y in 0..height {
            let line: String = (0..width).map(|x| buffer[(x, y)].symbol()).collect();
            println!("{}", line.trim_end());
        }
        return Ok(());
    }
    if !io::stdin().is_terminal() || !io::stdout().is_terminal() {
        eprintln!("Open this interface in a terminal, or use --render for a design preview.");
        return Ok(());
    }
    let mut terminal = ratatui::init();
    execute!(io::stdout(), EnableMouseCapture)?;
    let result = event_loop(&mut terminal, &mut app);
    ratatui::restore();
    execute!(io::stdout(), DisableMouseCapture)?;
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    fn app() -> App {
        App::new(
            Backend {
                python: "must-never-run".into(),
                share: "unused".into(),
            },
            true,
        )
    }
    #[test]
    fn welcome_names_both_paths() {
        let mut terminal = Terminal::new(TestBackend::new(110, 32)).unwrap();
        terminal.draw(|f| render(f, &app())).unwrap();
        let text = format!("{:?}", terminal.backend().buffer());
        assert!(text.contains("Guided setup"));
        assert!(text.contains("Direct agent conversation"));
    }
    #[test]
    fn linux_console_uses_legible_sixteen_color_selection() {
        assert_eq!(console_color(MUTED), Color::Gray);
        assert_eq!(console_color(TEXT), Color::White);
        let mut app = app();
        app.console_palette = true;
        let mut terminal = Terminal::new(TestBackend::new(160, 50)).unwrap();
        terminal.draw(|f| render(f, &app)).unwrap();
        let cells = &terminal.backend().buffer().content;
        assert!(
            cells
                .iter()
                .all(|c| !matches!(c.fg, Color::Rgb(..)) && !matches!(c.bg, Color::Rgb(..)))
        );
        assert!(cells.iter().any(|c| c.bg == Color::Blue));
        assert!(cells.iter().any(|c| c.fg == Color::LightCyan));
    }
    #[test]
    fn every_page_renders_on_console_and_small_terminals() {
        for (w, h) in [(110, 36), (80, 25), (55, 18), (40, 12)] {
            for page in [
                Page::Welcome,
                Page::Help,
                Page::View(0),
                Page::View(1),
                Page::View(2),
                Page::View(3),
                Page::View(4),
                Page::View(5),
                Page::View(6),
                Page::View(7),
            ] {
                let mut a = app();
                a.page = page;
                let mut t = Terminal::new(TestBackend::new(w, h)).unwrap();
                t.draw(|f| render(f, &a)).unwrap();
            }
        }
    }
    #[test]
    fn preview_applies_custom_without_running_a_backend() {
        let mut a = app();
        a.request("preset", &["custom".into()]);
        assert!(a.data["handoff"]["choices"].as_object().unwrap().is_empty());
        assert!(a.job.is_none());
    }
    #[test]
    fn preset_replacement_requires_confirmation() {
        let mut a = app();
        a.request("preset", &["familiar".into()]);
        a.preset = 2;
        a.apply_preset();
        assert!(matches!(a.prompt, Some(Prompt::ConfirmPreset(_))));
        handle_prompt(&mut a, KeyCode::Esc);
        assert_eq!(a.data["handoff"]["preset"], "familiar");
    }
    #[test]
    fn export_is_cancelled_by_default() {
        let mut a = app();
        a.prompt = Some(Prompt::ConfirmExport("/fixture".into(), "digest".into()));
        handle_prompt(&mut a, KeyCode::Enter);
        assert!(a.prompt.is_some());
        handle_prompt(&mut a, KeyCode::Char('n'));
        assert!(a.prompt.is_none());
        assert!(a.job.is_none());
    }
    #[test]
    fn preview_paths_are_data_without_commands() {
        let mut a = app();
        a.prompt_input(Prompt::Import);
        for c in "$(touch fixture)".chars() {
            handle_prompt(&mut a, KeyCode::Char(c));
        }
        handle_prompt(&mut a, KeyCode::Enter);
        assert!(a.job.is_none());
        assert!(a.message.contains("no system commands"));
    }
}
