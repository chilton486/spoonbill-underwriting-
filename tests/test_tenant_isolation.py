import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.practice import Practice
from app.models.claim import Claim, ClaimStatus
from app.models.document import ClaimDocument
from app.services.auth import AuthService

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def practice_a(db):
    practice = Practice(name="Practice A")
    db.add(practice)
    db.commit()
    db.refresh(practice)
    return practice


@pytest.fixture
def practice_b(db):
    practice = Practice(name="Practice B")
    db.add(practice)
    db.commit()
    db.refresh(practice)
    return practice


@pytest.fixture
def practice_manager_a(db, practice_a):
    user = User(
        email="manager_a@practice-a.com",
        password_hash=AuthService.get_password_hash("password123"),
        role=UserRole.PRACTICE_MANAGER.value,
        practice_id=practice_a.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def practice_manager_b(db, practice_b):
    user = User(
        email="manager_b@practice-b.com",
        password_hash=AuthService.get_password_hash("password123"),
        role=UserRole.PRACTICE_MANAGER.value,
        practice_id=practice_b.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def spoonbill_admin(db):
    user = User(
        email="admin@spoonbill.com",
        password_hash=AuthService.get_password_hash("password123"),
        role=UserRole.SPOONBILL_ADMIN.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def claim_practice_a(db, practice_a):
    claim = Claim(
        practice_id=practice_a.id,
        payer="Aetna",
        amount_cents=10000,
        status=ClaimStatus.NEW.value,
        fingerprint="practice_a_claim_1",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


@pytest.fixture
def claim_practice_b(db, practice_b):
    claim = Claim(
        practice_id=practice_b.id,
        payer="BCBS",
        amount_cents=20000,
        status=ClaimStatus.NEW.value,
        fingerprint="practice_b_claim_1",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


@pytest.fixture
def document_practice_a(db, claim_practice_a, practice_a, practice_manager_a):
    doc = ClaimDocument(
        claim_id=claim_practice_a.id,
        practice_id=practice_a.id,
        filename="test_doc_a.pdf",
        content_type="application/pdf",
        storage_path="/tmp/test_doc_a.pdf",
        uploaded_by_user_id=practice_manager_a.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@pytest.fixture
def document_practice_b(db, claim_practice_b, practice_b, practice_manager_b):
    doc = ClaimDocument(
        claim_id=claim_practice_b.id,
        practice_id=practice_b.id,
        filename="test_doc_b.pdf",
        content_type="application/pdf",
        storage_path="/tmp/test_doc_b.pdf",
        uploaded_by_user_id=practice_manager_b.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_token(client, email, password):
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestPracticeManagerClaimIsolation:
    def test_practice_a_cannot_read_practice_b_claim_list(
        self, client, practice_manager_a, practice_manager_b, claim_practice_a, claim_practice_b
    ):
        token_a = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.get(
            "/practice/claims",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response.status_code == 200
        claims = response.json()
        
        claim_ids = [c["id"] for c in claims]
        assert claim_practice_a.id in claim_ids
        assert claim_practice_b.id not in claim_ids

    def test_practice_a_cannot_read_practice_b_claim_by_id(
        self, client, practice_manager_a, claim_practice_b
    ):
        token_a = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.get(
            f"/practice/claims/{claim_practice_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Claim not found"

    def test_practice_a_cannot_read_practice_b_claim_by_guessing_id(
        self, client, practice_manager_a, claim_practice_b
    ):
        token_a = get_token(client, "manager_a@practice-a.com", "password123")
        
        for guessed_id in [claim_practice_b.id, claim_practice_b.id + 1, 9999]:
            response = client.get(
                f"/practice/claims/{guessed_id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 404

    def test_practice_b_can_read_own_claims(
        self, client, practice_manager_b, claim_practice_b
    ):
        token_b = get_token(client, "manager_b@practice-b.com", "password123")
        
        response = client.get(
            f"/practice/claims/{claim_practice_b.id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == claim_practice_b.id


class TestPracticeManagerDocumentIsolation:
    def test_practice_a_cannot_list_practice_b_documents(
        self, client, practice_manager_a, claim_practice_b, document_practice_b
    ):
        token_a = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.get(
            f"/practice/claims/{claim_practice_b.id}/documents",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response.status_code == 404

    def test_practice_a_cannot_download_practice_b_document(
        self, client, practice_manager_a, document_practice_b
    ):
        token_a = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.get(
            f"/practice/documents/{document_practice_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Document not found"

    def test_practice_a_cannot_download_practice_b_document_by_guessing_id(
        self, client, practice_manager_a, document_practice_b
    ):
        token_a = get_token(client, "manager_a@practice-a.com", "password123")
        
        for guessed_id in [document_practice_b.id, document_practice_b.id + 1, 9999]:
            response = client.get(
                f"/practice/documents/{guessed_id}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 404

    def test_practice_a_cannot_upload_to_practice_b_claim(
        self, client, practice_manager_a, claim_practice_b
    ):
        token_a = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.post(
            f"/practice/claims/{claim_practice_b.id}/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("test.txt", b"test content", "text/plain")},
        )
        assert response.status_code == 404


class TestSpoonbillUserAccess:
    def test_spoonbill_admin_can_access_all_claims(
        self, client, spoonbill_admin, claim_practice_a, claim_practice_b
    ):
        token = get_token(client, "admin@spoonbill.com", "password123")
        
        response = client.get(
            "/api/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        claims = response.json()
        
        claim_ids = [c["id"] for c in claims]
        assert claim_practice_a.id in claim_ids
        assert claim_practice_b.id in claim_ids

    def test_spoonbill_admin_can_filter_by_practice(
        self, client, spoonbill_admin, practice_a, claim_practice_a, claim_practice_b
    ):
        token = get_token(client, "admin@spoonbill.com", "password123")
        
        response = client.get(
            f"/api/claims?practice_id={practice_a.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        claims = response.json()
        
        claim_ids = [c["id"] for c in claims]
        assert claim_practice_a.id in claim_ids
        assert claim_practice_b.id not in claim_ids

    def test_practice_manager_cannot_access_internal_api(
        self, client, practice_manager_a
    ):
        token = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.get(
            "/api/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestClaimSubmissionIsolation:
    def test_practice_manager_claim_gets_their_practice_id(
        self, client, db, practice_manager_a, practice_a
    ):
        token = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.post(
            "/practice/claims",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "payer": "Cigna",
                "amount_cents": 15000,
            },
        )
        assert response.status_code == 201
        claim = response.json()
        
        assert claim["practice_id"] == practice_a.id

    def test_practice_manager_cannot_submit_claim_for_other_practice(
        self, client, practice_manager_a, practice_b
    ):
        token = get_token(client, "manager_a@practice-a.com", "password123")
        
        response = client.post(
            "/practice/claims",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "payer": "Cigna",
                "amount_cents": 15000,
            },
        )
        assert response.status_code == 201
        claim = response.json()
        
        assert claim["practice_id"] != practice_b.id
