# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-09-01 16:29
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import items.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tagging', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Author',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=255)),
                ('middle_initials', models.CharField(blank=True, max_length=31, null=True)),
                ('last_name', models.CharField(max_length=255)),
                ('slug', models.SlugField(editable=False, max_length=510)),
            ],
            options={
                'ordering': ['last_name'],
            },
        ),
        migrations.CreateModel(
            name='AuthorGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=0)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='items.Author')),
            ],
        ),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.TextField()),
                ('slug', models.SlugField(editable=False, max_length=255)),
                ('item_type', models.CharField(choices=[('thesis', 'Thesis'), ('journalpub', 'Journal publication'), ('book', 'Book'), ('conferenceproc', 'Conference proceeding')], max_length=20)),
                ('year', models.PositiveIntegerField()),
                ('doi_link', models.URLField(blank=True, null=True, verbose_name='DOI link')),
                ('web_link', models.URLField(blank=True, null=True)),
                ('abstract', models.TextField(blank=True)),
                ('show_abstract', models.BooleanField(default=False)),
                ('date_created', models.DateTimeField(auto_now=True)),
                ('pdf_file', models.FileField(blank=True, max_length=255, null=True, upload_to=items.models.Item.upload_dest, verbose_name='PDF file')),
                ('private_pdf', models.BooleanField(default=False, verbose_name='Private PDF')),
                ('other_search_text', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Journal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=510)),
                ('website', models.URLField()),
                ('slug', models.SlugField(editable=False, max_length=510)),
            ],
        ),
        migrations.CreateModel(
            name='Publisher',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=510)),
                ('slug', models.SlugField(editable=False, max_length=510)),
            ],
        ),
        migrations.CreateModel(
            name='School',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(editable=False, max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Book',
            fields=[
                ('item_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='items.Item')),
                ('volume', models.CharField(blank=True, max_length=100, null=True)),
                ('series', models.CharField(blank=True, max_length=100, null=True)),
                ('edition', models.CharField(blank=True, max_length=100, null=True)),
                ('isbn', models.CharField(blank=True, max_length=20, null=True, verbose_name='ISBN')),
                ('editors', models.ManyToManyField(blank=True, to='items.Author')),
                ('publisher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='items.Publisher')),
            ],
            bases=('items.item',),
        ),
        migrations.CreateModel(
            name='ConferenceProceeding',
            fields=[
                ('item_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='items.Item')),
                ('conference_name', models.CharField(blank=True, max_length=255, null=True)),
                ('page_start', models.CharField(blank=True, max_length=10, null=True)),
                ('page_end', models.CharField(blank=True, max_length=10, null=True)),
                ('organization', models.CharField(blank=True, max_length=200, null=True)),
                ('location', models.CharField(blank=True, max_length=200, null=True)),
                ('editors', models.ManyToManyField(blank=True, to='items.Author')),
                ('publisher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='items.Publisher')),
            ],
            options={
                'verbose_name_plural': 'conference proceedings',
            },
            bases=('items.item',),
        ),
        migrations.CreateModel(
            name='JournalPub',
            fields=[
                ('item_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='items.Item')),
                ('volume', models.CharField(blank=True, max_length=100, null=True)),
                ('page_start', models.CharField(blank=True, max_length=10, null=True)),
                ('page_end', models.CharField(blank=True, max_length=10, null=True)),
                ('journal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='items.Journal')),
            ],
            options={
                'verbose_name_plural': 'journal publications',
            },
            bases=('items.item',),
        ),
        migrations.CreateModel(
            name='Thesis',
            fields=[
                ('item_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='items.Item')),
                ('thesis_type', models.CharField(choices=[('masters', 'Masters thesis'), ('phd', 'Ph.D thesis')], max_length=50)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='items.School')),
                ('supervisors', models.ManyToManyField(blank=True, to='items.Author')),
            ],
            options={
                'verbose_name_plural': 'theses',
            },
            bases=('items.item',),
        ),
        migrations.AddField(
            model_name='item',
            name='authors',
            field=models.ManyToManyField(through='items.AuthorGroup', to='items.Author'),
        ),
        migrations.AddField(
            model_name='item',
            name='tags',
            field=models.ManyToManyField(to='tagging.Tag'),
        ),
        migrations.AddField(
            model_name='authorgroup',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='items.Item'),
        ),
    ]