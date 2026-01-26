"""Tests for project service."""

import pytest

from src.models import ProjectStatus, GuardrailStatus
from src.services import (
    IntakeData,
    create_project,
    create_project_from_intake,
    get_project,
    get_project_with_sessions,
    update_project_status,
    approve_project,
    reject_project,
    list_projects,
)


class TestCreateProject:
    def test_creates_project(self, active_client, db_session):
        data = IntakeData(project_name="New Project")
        project = create_project(active_client.id, data)
        
        assert project.name == "New Project"
        assert project.client_id == active_client.id
        assert project.status == ProjectStatus.INTAKE

    def test_creates_with_all_fields(self, active_client, db_session):
        data = IntakeData(
            project_name="Full Project",
            repo_url="https://github.com/test/full",
            description="A full project",
            tech_stack="Python",
            access_method="github_invite",
            coding_standards="PEP8",
            do_not_touch="legacy/"
        )
        project = create_project(active_client.id, data)
        
        assert project.repo_url == "https://github.com/test/full"
        assert project.tech_stack == "Python"

    def test_raises_for_missing_client(self, db_session):
        data = IntakeData(project_name="Orphan")
        with pytest.raises(ValueError, match="not found"):
            create_project(9999, data)


class TestCreateProjectFromIntake:
    def test_creates_for_existing_client(self, active_client, db_session):
        data = IntakeData(project_name="Intake Project")
        project = create_project_from_intake("active@example.com", data)
        
        assert project is not None
        assert project.name == "Intake Project"

    def test_returns_none_for_missing_email(self, db_session):
        data = IntakeData(project_name="Orphan")
        project = create_project_from_intake("missing@example.com", data)
        
        assert project is None


class TestGetProject:
    def test_returns_project(self, sample_project):
        found = get_project(sample_project.id)
        assert found is not None
        assert found.id == sample_project.id

    def test_returns_none_for_missing(self, db_session):
        found = get_project(9999)
        assert found is None


class TestUpdateProjectStatus:
    def test_updates_status(self, sample_project):
        updated = update_project_status(sample_project.id, ProjectStatus.ACTIVE)
        assert updated.status == ProjectStatus.ACTIVE

    def test_raises_for_missing(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            update_project_status(9999, ProjectStatus.ACTIVE)


class TestApproveProject:
    def test_sets_status_to_active(self, sample_project):
        approved = approve_project(sample_project.id)
        assert approved.status == ProjectStatus.ACTIVE

    def test_raises_for_missing(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            approve_project(9999)


class TestRejectProject:
    def test_sets_status_to_paused(self, sample_project):
        rejected = reject_project(sample_project.id, "Not allowed")
        assert rejected.status == ProjectStatus.PAUSED

    def test_raises_for_missing(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            reject_project(9999, "No reason")


class TestListProjects:
    def test_returns_all_projects(self, sample_project, db_session):
        projects, total = list_projects()
        assert total >= 1

    def test_filters_by_status(self, sample_project, db_session):
        projects, total = list_projects(status=ProjectStatus.INTAKE)
        assert all(p.status == ProjectStatus.INTAKE for p in projects)

    def test_filters_by_client(self, sample_project, db_session):
        projects, total = list_projects(client_id=sample_project.client_id)
        assert all(p.client_id == sample_project.client_id for p in projects)
