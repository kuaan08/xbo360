// Xbox 360 Recomp — Copyright 2026 katakishi0, hosted by kuaan08.
// Frontend derived from SwitchRecomp by MZ Labs (Apache-2.0).
// Modified: Xbox 360 project workflow, ReXGlue SDK, project persistence and Xbox theme.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod icon;
mod job;
mod theme;
mod toolchain;

use eframe::egui::{self, RichText};
use serde::{Deserialize, Serialize};
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::time::Duration;

#[derive(Default, Serialize, Deserialize)]
#[serde(default)]
struct Settings {
    input: String,
    game_root: String,
    project: String,
    name: String,
    sdk: String,
    python: String,
    projects: Vec<String>,
    renderer: String,
    jobs: u32,
}

struct App {
    settings: Settings,
    settings_path: PathBuf,
    job: Option<job::Job>,
    progress: job::Progress,
    log: Vec<String>,
    tab: usize,
}

impl App {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        theme::apply(&cc.egui_ctx);
        let base = std::env::var_os("LOCALAPPDATA")
            .or_else(|| std::env::var_os("XDG_CONFIG_HOME"))
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".config")
            });
        let settings_path = base.join("Xbox360Recomp").join("settings.json");
        let mut settings: Settings = std::fs::read(&settings_path)
            .ok()
            .and_then(|b| serde_json::from_slice(&b).ok())
            .unwrap_or_default();
        if settings.python.is_empty() {
            settings.python = toolchain::python().to_string_lossy().into_owned();
        }
        if settings.renderer.is_empty() {
            settings.renderer = "any".into();
        }
        if settings.name.is_empty() {
            settings.name = "my_game".into();
        }
        Self {
            settings,
            settings_path,
            job: None,
            progress: Default::default(),
            log: vec![],
            tab: 0,
        }
    }

    fn save(&mut self) {
        let result = (|| -> std::io::Result<()> {
            if let Some(p) = self.settings_path.parent() {
                std::fs::create_dir_all(p)?;
            }
            std::fs::write(
                &self.settings_path,
                serde_json::to_vec_pretty(&self.settings)?,
            )
        })();
        if let Err(e) = result {
            self.log
                .push(format!("Warning: settings could not be saved: {e}"));
        }
    }

    fn start(&mut self, ctx: &egui::Context, args: Vec<String>) {
        if self.job.is_some() {
            return;
        }
        self.save();
        let cfg = job::JobConfig {
            python: self.settings.python.clone().into(),
            home: toolchain::home(),
            args: args.into_iter().map(OsString::from).collect(),
        };
        self.log.clear();
        self.log.push(format!("> {}", cfg.display()));
        self.progress = Default::default();
        match job::Job::start(&cfg, ctx) {
            Ok(j) => self.job = Some(j),
            Err(e) => {
                self.log.push(format!("Error: {e}"));
                self.progress.phase = job::Phase::Failed;
            }
        }
    }

    fn sdk_args(&self, args: &mut Vec<String>) {
        if !self.settings.sdk.trim().is_empty() {
            args.extend(["--sdk".into(), self.settings.sdk.clone()]);
        }
    }

    fn create(&mut self, ctx: &egui::Context, stage: &str) {
        let s = &self.settings;
        let mut args = vec![
            stage.into(),
            s.input.clone(),
            "--project".into(),
            s.project.clone(),
            "--name".into(),
            s.name.clone(),
        ];
        if !s.game_root.trim().is_empty() {
            args.extend(["--game-root".into(), s.game_root.clone()]);
        }
        self.sdk_args(&mut args);
        if !self.settings.projects.contains(&self.settings.project)
            && !self.settings.project.is_empty()
        {
            self.settings.projects.push(self.settings.project.clone());
        }
        self.start(ctx, args);
    }

    fn poll(&mut self) {
        let mut exited = None;
        if let Some(j) = &self.job {
            for event in j.events() {
                match event {
                    job::JobEvent::Line(s) => {
                        self.progress.feed(&s);
                        self.log.push(s);
                        if self.log.len() > 8000 {
                            self.log.drain(..1000);
                        }
                    }
                    job::JobEvent::Exited(code) => exited = Some((code, j.cancelled)),
                }
            }
        }
        if let Some((code, cancelled)) = exited {
            self.progress.phase = if cancelled {
                job::Phase::Cancelled
            } else if code == Some(0) {
                job::Phase::Done
            } else {
                job::Phase::Failed
            };
            self.log.push(format!("Process exited: {code:?}"));
            self.job = None;
        }
    }

    fn new_project(&mut self, ui: &mut egui::Ui, ctx: &egui::Context) {
        ui.heading("Recompile an Xbox 360 title");
        ui.label("Select an extracted XEX and a separate project folder.");
        ui.add_space(10.0);
        field(
            ui,
            "Xbox 360 executable",
            &mut self.settings.input,
            false,
            true,
        );
        field(
            ui,
            "Game data directory (optional)",
            &mut self.settings.game_root,
            true,
            false,
        );
        field(
            ui,
            "Project directory (empty)",
            &mut self.settings.project,
            true,
            false,
        );
        ui.label("Project name (lowercase, for example my_game)");
        ui.text_edit_singleline(&mut self.settings.name);
        ui.add_space(10.0);
        ui.horizontal(|ui| {
            if ui.button("Inspect XEX").clicked() {
                self.start(ctx, vec!["inspect".into(), self.settings.input.clone()]);
            }
            if ui.button("Prepare project").clicked() {
                self.create(ctx, "prepare");
            }
            if ui
                .add(
                    egui::Button::new(RichText::new("Recompile + build").color(theme::BG))
                        .fill(theme::ACCENT),
                )
                .clicked()
            {
                self.create(ctx, "recompile");
            }
        });
        ui.add_space(10.0);
        ui.colored_label(
            theme::WARNING,
            "Experimental: each title may need function boundaries, hooks and runtime fixes.",
        );
    }

    fn projects(&mut self, ui: &mut egui::Ui, ctx: &egui::Context) {
        ui.heading("Projects");
        if ui.button("Open existing project...").clicked()
            && let Some(p) = rfd::FileDialog::new().pick_folder()
        {
            let s = p.to_string_lossy().to_string();
            if !self.settings.projects.contains(&s) {
                self.settings.projects.push(s);
                self.save();
            }
        }
        for root in self.settings.projects.clone() {
            let path = Path::new(&root);
            let state = std::fs::read(path.join("xbo360-project.json"))
                .ok()
                .and_then(|b| serde_json::from_slice::<serde_json::Value>(&b).ok());
            egui::Frame::group(ui.style()).show(ui, |ui| {
                let name = state
                    .as_ref()
                    .and_then(|s| s["name"].as_str())
                    .unwrap_or("Project");
                let status = state
                    .as_ref()
                    .and_then(|s| s["status"].as_str())
                    .unwrap_or("not prepared");
                ui.label(RichText::new(name).strong());
                ui.label(format!("{status} · {root}"));
                ui.horizontal(|ui| {
                    if ui
                        .add_enabled(state.is_some(), egui::Button::new("Generate C++"))
                        .clicked()
                    {
                        let mut args = vec!["codegen".into(), root.clone()];
                        self.sdk_args(&mut args);
                        self.start(ctx, args);
                    }
                    if ui
                        .add_enabled(state.is_some(), egui::Button::new("Build"))
                        .clicked()
                    {
                        let mut args = vec![
                            "build".into(),
                            root.clone(),
                            "--jobs".into(),
                            self.settings.jobs.to_string(),
                        ];
                        self.sdk_args(&mut args);
                        self.start(ctx, args);
                    }
                    if ui
                        .add_enabled(status == "built", egui::Button::new("Run"))
                        .clicked()
                    {
                        self.start(
                            ctx,
                            vec![
                                "run".into(),
                                root.clone(),
                                "--renderer".into(),
                                self.settings.renderer.clone(),
                            ],
                        );
                    }
                    if ui.button("Open folder").clicked() {
                        open_path(path);
                    }
                });
            });
        }
    }

    fn settings_ui(&mut self, ui: &mut egui::Ui, ctx: &egui::Context) {
        ui.heading("Tools and runtime");
        field(ui, "Python 3.11+", &mut self.settings.python, false, false);
        field(
            ui,
            "ReXGlue 0.10.0 SDK prefix (blank = bundled/cache)",
            &mut self.settings.sdk,
            true,
            false,
        );
        ui.horizontal(|ui| {
            if ui.button("Install verified SDK").clicked() {
                let mut args = vec!["install-sdk".into()];
                self.sdk_args(&mut args);
                self.start(ctx, args);
            }
            if ui.button("Check toolchain").clicked() {
                let mut args = vec!["doctor".into()];
                self.sdk_args(&mut args);
                self.start(ctx, args);
            }
            if ui.button("Save settings").clicked() {
                self.save();
            }
        });
        ui.label("Build jobs (0 = automatic)");
        ui.add(egui::DragValue::new(&mut self.settings.jobs).range(0..=256));
        egui::ComboBox::from_label("Renderer at launch")
            .selected_text(&self.settings.renderer)
            .show_ui(ui, |ui| {
                ui.selectable_value(&mut self.settings.renderer, "any".into(), "Automatic");
                if cfg!(windows) {
                    ui.selectable_value(&mut self.settings.renderer, "d3d12".into(), "Direct3D 12");
                }
                ui.selectable_value(&mut self.settings.renderer, "vulkan".into(), "Vulkan");
            });
        ui.label("The chosen backend must be present in your SDK's Xenos plugin.");
        ui.label("Windows builds need Visual Studio 2022 C++, Clang 20+, CMake and Ninja.");
        ui.label("Launch the workbench from an x64 Native Tools command prompt when building.");
    }
}

impl eframe::App for App {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();
        self.poll();
        if self.job.is_some() {
            ctx.request_repaint_after(Duration::from_millis(100));
        }
        ui.heading(RichText::new("XBOX 360 RECOMP").color(theme::ACCENT));
        ui.label("PowerPC → C++ → native PC · powered by ReXGlue");
        ui.horizontal(|ui| {
            for (i, label) in ["New project", "Projects", "Settings", "About"]
                .iter()
                .enumerate()
            {
                if ui.selectable_label(self.tab == i, *label).clicked() {
                    self.tab = i;
                }
            }
        });
        ui.separator();
        let running = self.job.is_some();
        ui.add_enabled_ui(!running, |ui| {
            egui::ScrollArea::vertical().id_salt("page").max_height(380.0).show(ui, |ui| match self.tab {
                0 => self.new_project(ui, &ctx),
                1 => self.projects(ui, &ctx),
                2 => self.settings_ui(ui, &ctx),
                _ => {
                    ui.heading("Xbox 360 Recomp 0.1.0");
                    ui.label("SwitchRecomp by MZ Labs — original frontend foundation (Apache-2.0).");
                    ui.label("Xbox 360 adaptation: katakishi0 · repository hosting: kuaan08.");
                    ui.label("ReXGlue by Tom Clay and contributors; based on Xenia and XenonRecomp research.");
                    ui.hyperlink("https://github.com/kuaan08/xbo360");
                    ui.label("This is a PC recompilation workbench. Android and Xbox console targets are not implemented.");
                    ui.label("No commercial game has been validated by this project yet.");
                }
            });
        });
        ui.separator();
        ui.horizontal(|ui| {
            if running {
                ui.spinner();
            }
            ui.label(self.progress.describe());
            if ui
                .add_enabled(running, egui::Button::new("Cancel process tree"))
                .clicked()
                && let Some(j) = self.job.as_mut()
            {
                j.cancel();
            }
            if ui.button("Save visible log").clicked()
                && let Some(path) = rfd::FileDialog::new()
                    .set_file_name("xbo360.log")
                    .save_file()
                && let Err(e) = std::fs::write(path, self.log.join("\n"))
            {
                self.log.push(format!("Error saving log: {e}"));
            }
        });
        egui::ScrollArea::vertical()
            .id_salt("log")
            .stick_to_bottom(true)
            .show(ui, |ui| {
                for line in &self.log {
                    let color = match job::classify(line) {
                        job::LineKind::Error => theme::ERROR,
                        job::LineKind::Warning => theme::WARNING,
                        job::LineKind::Success => theme::SUCCESS,
                        job::LineKind::Command => theme::ACCENT,
                        _ => theme::TEXT_WEAK,
                    };
                    ui.label(RichText::new(line).monospace().size(12.0).color(color));
                }
            });
    }
}

impl Drop for App {
    fn drop(&mut self) {
        self.save();
        if let Some(j) = &mut self.job {
            j.cancel();
        }
    }
}

fn field(ui: &mut egui::Ui, label: &str, value: &mut String, folder: bool, xex: bool) {
    ui.label(label);
    ui.horizontal(|ui| {
        ui.add(
            egui::TextEdit::singleline(value)
                .desired_width((ui.available_width() - 90.0).max(180.0)),
        );
        if ui.button("Browse...").clicked() {
            let dialog = rfd::FileDialog::new();
            let selected = if folder {
                dialog.pick_folder()
            } else if xex {
                dialog
                    .add_filter("Xbox 360 executable", &["xex"])
                    .pick_file()
            } else {
                dialog.pick_file()
            };
            if let Some(p) = selected {
                *value = p.to_string_lossy().into_owned();
            }
        }
    });
}

fn open_path(path: &Path) {
    let mut command = if cfg!(windows) {
        std::process::Command::new("explorer")
    } else {
        std::process::Command::new("xdg-open")
    };
    let _ = command.arg(path).spawn();
}

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("Xbox 360 Recomp")
            .with_inner_size([1060.0, 800.0])
            .with_min_inner_size([800.0, 640.0])
            .with_icon(theme::app_icon()),
        ..Default::default()
    };
    eframe::run_native(
        "Xbox360Recomp",
        options,
        Box::new(|cc| Ok(Box::new(App::new(cc)))),
    )
}
