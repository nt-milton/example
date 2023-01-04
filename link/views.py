from django.shortcuts import render


def error_404(request, exception):
    return render(
        request,
        '404.html',
        {'title': 'This link is invalid!', 'subtitle': 'Please request a new link.'},
        status=404,
    )
