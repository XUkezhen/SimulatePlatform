from .models import Link  # 替换为你的模型模块路径

if __name__ == "__main__":
    Link.objects.all().delete()

    # python manage.py shell < delete.py