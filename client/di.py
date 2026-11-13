"""Composition root: сборка зависимостей слоёв."""
from types import SimpleNamespace

from .application import usecases as uc
from .infrastructure import repositories as impl
from .infrastructure.network import NetworkClient
from .infrastructure.session import SessionStore


def build_container(data_dir):
    net = NetworkClient()
    users = impl.UserRepositoryImpl(net, SessionStore(data_dir))
    ads = impl.AdRepositoryImpl(net)
    chats = impl.ChatRepositoryImpl(net)
    return SimpleNamespace(
        auth=uc.AuthUseCases(users),
        create_ad=uc.CreateAdUseCase(ads),
        feed=uc.FeedUseCases(ads),
        respond=uc.RespondToAdUseCase(ads),
        close=uc.CloseAdUseCase(ads),
        report=uc.ReportAdUseCase(ads),
        chats=uc.ChatUseCases(chats),
        send=uc.SendMessageUseCase(chats),
        moderate=uc.ModerateAdUseCase(impl.ModerationRepositoryImpl(net)),
        notifications=uc.PollNotificationsUseCase(impl.NotificationRepositoryImpl(net)),
    )
