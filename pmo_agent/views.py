from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """VeriRAG PMO Agent の統一UIプロトタイプを独立フルページで配信する。

    MVPは自己完結した ``<!doctype html>`` 文書であり ``base.html`` は継承しない。
    デモ値の自己補完とlocalStorage永続化はテンプレート内蔵JSが担うため、
    サーバー側の追加配線なしで見た目・クライアント機能をそのまま反映する。
    """
    return render(request, "pmo_agent/mvp.html")
