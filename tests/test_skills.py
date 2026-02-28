from skills.loader import Skill, load_skills


def test_load_skills_count():
    skills = load_skills("skills")
    assert len(skills) >= 7


def test_skill_has_required_fields():
    skills = load_skills("skills")
    for skill in skills:
        assert isinstance(skill, Skill)
        assert skill.name
        assert skill.description
        assert skill.body
        assert skill.file_path.exists()


def test_skill_names():
    skills = load_skills("skills")
    names = {s.name for s in skills}
    expected = {"system-debug", "web-research", "deploy", "project-setup", "file-ops", "home-assistant", "self-demo"}
    assert expected.issubset(names)


def test_skill_frontmatter_parse():
    skills = load_skills("skills")
    for skill in skills:
        assert len(skill.body) > 50, f"{skill.name} body too short"


def test_self_demo_has_acts():
    skills = load_skills("skills")
    demo = next(s for s in skills if s.name == "self-demo")
    assert "Act 1" in demo.body
    assert "Act 6" in demo.body
    assert "Closing" in demo.body


def test_system_debug_has_steps():
    skills = load_skills("skills")
    debug = next(s for s in skills if s.name == "system-debug")
    assert "Step 1" in debug.body
    assert "nvidia-smi" in debug.body


def test_home_assistant_has_domains():
    skills = load_skills("skills")
    ha = next(s for s in skills if s.name == "home-assistant")
    assert "ha_call_service" in ha.body
    assert "ha_get_states" in ha.body
