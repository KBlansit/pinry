# index_together was removed in Django 5.1. The (submitter, name) pair is
# already covered by the unique_together index, so only drop it from the
# migration state; any legacy index left in existing databases is harmless.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_auto_20210311_1521'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterIndexTogether(
                    name='board',
                    index_together=set(),
                ),
            ],
        ),
    ]
