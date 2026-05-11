"""Test fixtures shared across the items test modules."""

import pytest

from items.models import (
    Author,
    AuthorGroup,
    Book,
    InCollection,
    Journal,
    JournalPub,
    Publisher,
    School,
)
from tagging.models import Tag


@pytest.fixture
def journal(db):
    return Journal.objects.create(name="Test Journal", website="https://example.com")


@pytest.fixture
def publisher(db):
    return Publisher.objects.create(name="Test Publisher")


@pytest.fixture
def school(db):
    return School.objects.create(name="McMaster University")


@pytest.fixture
def author(db):
    return Author.objects.create(first_name="Albert", last_name="Einstein")


@pytest.fixture
def two_authors(db):
    a1 = Author.objects.create(first_name="Albert", last_name="Einstein")
    a2 = Author.objects.create(first_name="Marie", last_name="Curie")
    return [a1, a2]


@pytest.fixture
def three_authors(db):
    a1 = Author.objects.create(first_name="James", last_name="Joyce")
    a2 = Author.objects.create(first_name="John", last_name="Smith")
    a3 = Author.objects.create(first_name="Tina", last_name="Smythe")
    return [a1, a2, a3]


@pytest.fixture
def tag(db):
    return Tag.objects.create(name="Fourier")


@pytest.fixture
def journalpub_factory(db, journal):
    """Create a JournalPub with the given authors / tags / kwargs."""

    def _make(authors=None, tags=None, **kwargs):
        defaults = dict(
            title="On Fourier transforms",
            item_type="journalpub",
            year=2024,
            abstract="<p>Harmonic analysis under <i>Lorentz</i> boosts.</p>",
            journal=journal,
        )
        defaults.update(kwargs)
        pub = JournalPub.objects.create(**defaults)
        if authors:
            for order, a in enumerate(authors):
                AuthorGroup.objects.create(author=a, item=pub, order=order)
        if tags:
            pub.tags.add(*tags)
        return pub

    return _make


@pytest.fixture
def book_factory(db, publisher):
    """Create a Book with the given authors / editors / tags / kwargs."""

    def _make(authors=None, editors=None, tags=None, **kwargs):
        defaults = dict(
            title="Multivariate Calibration",
            item_type="book",
            year=2017,
            edition="2nd edition",
            isbn="978-1-234-56789-0",
            publisher=publisher,
        )
        defaults.update(kwargs)
        book = Book.objects.create(**defaults)
        if authors:
            for order, a in enumerate(authors):
                AuthorGroup.objects.create(author=a, item=book, order=order)
        if editors:
            book.editors.add(*editors)
        if tags:
            book.tags.add(*tags)
        return book

    return _make


@pytest.fixture
def incollection_factory(db, publisher):
    """Create an InCollection (book chapter) with authors / editors / tags."""

    def _make(authors=None, editors=None, tags=None, **kwargs):
        defaults = dict(
            title="Soft sensors in batch processes",
            item_type="incollection",
            year=2018,
            book_title="Multivariate Statistical Methods for Process Modelling",
            publisher=publisher,
            page_start="123",
            page_end="155",
        )
        defaults.update(kwargs)
        chap = InCollection.objects.create(**defaults)
        if authors:
            for order, a in enumerate(authors):
                AuthorGroup.objects.create(author=a, item=chap, order=order)
        if editors:
            chap.editors.add(*editors)
        if tags:
            chap.tags.add(*tags)
        return chap

    return _make
