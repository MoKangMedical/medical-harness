"""OpenArena readiness and submission integration."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .env import getenv, getenv_bool, load_dotenv


OPENARENA_BASE_URL = "https://openarena.to"
DEFAULT_ROUTER_STATE_TREE = (
    '%5B%22%22%2C%7B%22children%22%3A%5B%22submit%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C0%5D%7D%2Cnull%2Cnull%2C1%5D'
)
STATUS_URL_RE = re.compile(r"^https://x\.com/[^/]+/status/\d+$")
GITHUB_REPO_RE = re.compile(r"^https://github\.com/[^/]+/[^/#?]+(?:/?|#.*)?$")


@dataclass
class OpenArenaProjectSubmission:
    x_post_url: str
    project_name: str
    github_repo_url: str
    project_website_url: str = ""
    team_contact: str = ""
    submitter_name: str = ""
    submitter_contact: str = ""
    submitter_payout_address: str = ""
    ranking_reason: str = ""
    team_aware: bool = True
    additional_notes: str = ""

    def to_api_payload(self) -> dict[str, Any]:
        website = self.project_website_url or f"{self.github_repo_url.rstrip('/') }#readme"
        return {
            "xPostUrl": self.x_post_url,
            "projectName": self.project_name,
            "projectWebsiteUrl": website,
            "githubRepoUrl": self.github_repo_url,
            "teamContact": self.team_contact,
            "submitterName": self.submitter_name,
            "submitterContact": self.submitter_contact,
            "submitterPayoutAddress": self.submitter_payout_address,
            "rankingReason": self.ranking_reason,
            "teamAware": self.team_aware,
            "additionalNotes": self.additional_notes,
        }


@dataclass
class OpenArenaReadinessReport:
    ready: bool
    score: int
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_runtime: list[str] = field(default_factory=list)
    submission_payload: dict[str, Any] = field(default_factory=dict)
    discovered_action_id: str | None = None


@dataclass
class OpenArenaSubmissionResult:
    success: bool
    submission_id: str | None = None
    error: str | None = None
    action_id: str | None = None
    raw_response: str = ""


OPENARENA_ENV_FIELDS: dict[str, str] = {
    "x_post_url": "OPENARENA_X_POST_URL",
    "project_name": "OPENARENA_PROJECT_NAME",
    "github_repo_url": "OPENARENA_GITHUB_REPO_URL",
    "project_website_url": "OPENARENA_PROJECT_WEBSITE_URL",
    "team_contact": "OPENARENA_TEAM_CONTACT",
    "submitter_name": "OPENARENA_SUBMITTER_NAME",
    "submitter_contact": "OPENARENA_SUBMITTER_CONTACT",
    "submitter_payout_address": "OPENARENA_SUBMITTER_PAYOUT_ADDRESS",
    "ranking_reason": "OPENARENA_RANKING_REASON",
    "additional_notes": "OPENARENA_ADDITIONAL_NOTES",
}


class OpenArenaClient:
    def __init__(
        self,
        *,
        base_url: str = OPENARENA_BASE_URL,
        client: httpx.Client | None = None,
        router_state_tree: str = DEFAULT_ROUTER_STATE_TREE,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.router_state_tree = router_state_tree

    def default_submission(self, overrides: dict[str, Any] | None = None) -> OpenArenaProjectSubmission:
        load_dotenv()
        values = {
            field_name: getenv(env_name, "")
            for field_name, env_name in OPENARENA_ENV_FIELDS.items()
        }
        values["project_name"] = values["project_name"] or "OpenClaw-Medical-Harness"
        values["github_repo_url"] = values["github_repo_url"] or "https://github.com/MoKangMedical/openclaw-medical-harness"
        values["team_aware"] = getenv_bool("OPENARENA_TEAM_AWARE", True)
        if overrides:
            values.update({key: value for key, value in overrides.items() if value is not None})
        return OpenArenaProjectSubmission(**values)

    def evaluate_submission(
        self,
        submission: OpenArenaProjectSubmission,
        *,
        include_runtime_status: bool = True,
        discover_action: bool = False,
    ) -> OpenArenaReadinessReport:
        payload = submission.to_api_payload()
        issues: list[str] = []
        warnings: list[str] = []
        missing_runtime: list[str] = []

        required_fields = {
            "x_post_url": submission.x_post_url,
            "project_name": submission.project_name,
            "github_repo_url": submission.github_repo_url,
            "team_contact": submission.team_contact,
            "submitter_name": submission.submitter_name,
            "submitter_contact": submission.submitter_contact,
            "submitter_payout_address": submission.submitter_payout_address,
            "ranking_reason": submission.ranking_reason,
        }
        for field_name, value in required_fields.items():
            if not value:
                issues.append(f"missing required field: {field_name}")

        if submission.x_post_url and not STATUS_URL_RE.match(submission.x_post_url):
            issues.append("x_post_url must be a full X status URL")
        if submission.github_repo_url and not GITHUB_REPO_RE.match(submission.github_repo_url):
            issues.append("github_repo_url must be a GitHub repository URL")
        if submission.ranking_reason and len(submission.ranking_reason.strip()) < 60:
            warnings.append("ranking_reason is short; OpenArena submissions usually need a stronger justification")
        if "@" not in submission.team_contact:
            warnings.append("team_contact should usually include an email or X handle")
        if not submission.team_aware:
            warnings.append("teamAware=false may reduce submission readiness")

        action_id = None
        if include_runtime_status:
            runtime = self._runtime_config()
            if not runtime["session_cookie"]:
                missing_runtime.append("OPENARENA_SESSION_COOKIE")
            if not runtime["action_id"] and not discover_action:
                missing_runtime.append("OPENARENA_NEXT_ACTION_ID")
            if discover_action:
                try:
                    action_id = self.discover_submit_action_id()
                except Exception as exc:  # pragma: no cover - network variability
                    warnings.append(f"unable to discover live OpenArena action id: {exc}")
            else:
                action_id = runtime["action_id"]

        score = max(0, 100 - len(issues) * 18 - len(warnings) * 6 - len(missing_runtime) * 10)
        return OpenArenaReadinessReport(
            ready=not issues and (not missing_runtime or action_id is not None),
            score=score,
            issues=issues,
            warnings=warnings,
            missing_runtime=missing_runtime,
            submission_payload=payload,
            discovered_action_id=action_id,
        )

    def evaluate_env_submission(self, *, discover_action: bool = False) -> OpenArenaReadinessReport:
        return self.evaluate_submission(
            self.default_submission(),
            include_runtime_status=True,
            discover_action=discover_action,
        )

    def discover_submit_action_id(self) -> str:
        page_html = self._request("GET", "/submit").text
        chunk_paths = sorted(set(re.findall(r"/_next/static/chunks/[^\"']+\.js", page_html)))
        action_pattern = re.compile(r"submitProjectAction[^0-9a-f]+([0-9a-f]{20,})")
        for chunk_path in chunk_paths:
            text = self._request("GET", chunk_path).text
            match = action_pattern.search(text)
            if match:
                return match.group(1)
        raise RuntimeError("submitProjectAction was not found in current OpenArena bundles")

    def submit(
        self,
        submission: OpenArenaProjectSubmission,
        *,
        session_cookie: str | None = None,
        action_id: str | None = None,
        router_state_tree: str | None = None,
        auto_discover_action: bool = True,
    ) -> OpenArenaSubmissionResult:
        runtime = self._runtime_config()
        cookie = session_cookie or runtime["session_cookie"]
        current_action = action_id or runtime["action_id"]
        if current_action is None and auto_discover_action:
            current_action = self.discover_submit_action_id()
        if not cookie:
            return OpenArenaSubmissionResult(success=False, error="missing OpenArena session cookie")
        if not current_action:
            return OpenArenaSubmissionResult(success=False, error="missing OpenArena action id")

        readiness = self.evaluate_submission(submission, include_runtime_status=False)
        if readiness.issues:
            return OpenArenaSubmissionResult(
                success=False,
                error="; ".join(readiness.issues),
                action_id=current_action,
            )

        headers = {
            "Accept": "text/x-component",
            "next-action": current_action,
            "next-router-state-tree": router_state_tree or self.router_state_tree,
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/submit",
            "Cookie": self._normalize_cookie(cookie),
        }
        body = json.dumps([submission.to_api_payload()])
        response = self._request("POST", "/submit", headers=headers, content=body)
        result_payload = self._extract_rsc_payload(response.text)
        return OpenArenaSubmissionResult(
            success=bool(result_payload.get("success")),
            submission_id=result_payload.get("submissionId"),
            error=result_payload.get("error"),
            action_id=current_action,
            raw_response=response.text,
        )

    def submit_from_env(
        self,
        *,
        overrides: dict[str, Any] | None = None,
        auto_discover_action: bool | None = None,
    ) -> OpenArenaSubmissionResult:
        runtime = self._runtime_config()
        submission = self.default_submission(overrides=overrides)
        discover = runtime["auto_discover_action"] if auto_discover_action is None else auto_discover_action
        return self.submit(
            submission,
            auto_discover_action=discover,
        )

    def _runtime_config(self) -> dict[str, str | bool | None]:
        env_path = load_dotenv()
        return {
            "session_cookie": getenv("OPENARENA_SESSION_COOKIE") or getenv("OPENARENA_SESSION"),
            "action_id": getenv("OPENARENA_NEXT_ACTION_ID") or getenv("OPENARENA_NEXT_ACTION"),
            "auto_discover_action": getenv_bool("OPENARENA_AUTO_DISCOVER_ACTION", False),
            "env_path": str(env_path) if env_path else None,
        }

    @staticmethod
    def _normalize_cookie(cookie: str) -> str:
        return cookie if "=" in cookie else f"openarena_session={cookie}"

    @staticmethod
    def _extract_rsc_payload(body: str) -> dict[str, Any]:
        for line in body.splitlines():
            if re.match(r"^\d+:", line):
                candidate = line.split(":", 1)[1]
                if candidate.startswith("{"):
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                    if "success" in parsed:
                        return parsed
        raise RuntimeError("unable to parse OpenArena RSC response")

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        if self.client is not None:
            response = self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        with httpx.Client(follow_redirects=True, timeout=20.0) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
