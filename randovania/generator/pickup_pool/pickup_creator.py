from __future__ import annotations

from typing import TYPE_CHECKING

from randovania.game_description.pickup import pickup_category
from randovania.game_description.resources.location_category import LocationCategory
from randovania.game_description.resources.pickup_entry import PickupEntry, PickupGeneratorParams, PickupModel
from randovania.games.game import RandovaniaGame
from randovania.games.prime2.patcher import echoes_items

if TYPE_CHECKING:
    from collections.abc import Sequence

    from randovania.game_description.pickup.ammo_pickup import AmmoPickupDefinition
    from randovania.game_description.pickup.standard_pickup import StandardPickupDefinition
    from randovania.game_description.resources.resource_database import ResourceDatabase
    from randovania.game_description.resources.resource_info import ResourceQuantity
    from randovania.layout.base.standard_pickup_state import StandardPickupState


def create_standard_pickup(
        pickup: StandardPickupDefinition,
        state: StandardPickupState,
        resource_database: ResourceDatabase,
        ammo: AmmoPickupDefinition | None,
        ammo_requires_main_item: bool,
) -> PickupEntry:
    """
    Creates a Pickup for the given MajorItem
    :param state:
    :param pickup:
    :param resource_database:
    :param ammo:
    :param ammo_requires_main_item:
    :return:
    """

    extra_resources = [
        (resource_database.get_item(ammo_name), ammo_count)
        for ammo_name, ammo_count in zip(pickup.ammo, state.included_ammo)
    ]
    extra_resources.extend(
        (resource_database.get_item(item), count)
        for item, count in pickup.additional_resources.items()
    )

    def _create_resources(base_resource: str | None) -> ResourceQuantity:
        # FIXME: hacky quantity for Hazard Shield
        quantity = 5 if pickup.name == "Hazard Shield" else 1
        return resource_database.get_item(base_resource), quantity

    return PickupEntry(
        name=pickup.name,
        progression=tuple(
            _create_resources(progression)
            for progression in pickup.progression
        ),
        extra_resources=tuple(extra_resources),
        model=PickupModel(
            game=resource_database.game_enum,
            name=pickup.model_name,
        ),
        pickup_category=pickup.pickup_category,
        broad_category=pickup.broad_category,
        unlocks_resource=pickup.unlocks_ammo,
        respects_lock=ammo_requires_main_item,
        resource_lock=ammo.create_resource_lock(resource_database) if ammo is not None else None,
        generator_params=PickupGeneratorParams(
            preferred_location_category=pickup.preferred_location_category,
            probability_offset=pickup.probability_offset,
            probability_multiplier=pickup.probability_multiplier * state.priority,
        ),
    )


def create_ammo_pickup(ammo: AmmoPickupDefinition,
                       ammo_count: Sequence[int],
                       requires_main_item: bool,
                       resource_database: ResourceDatabase,
                       ) -> PickupEntry:
    """
    Creates a Pickup for an expansion of the given ammo.
    :param ammo:
    :param ammo_count:
    :param requires_main_item:
    :param resource_database:
    :return:
    """
    resources = [(resource_database.get_item(item), count)
                 for item, count in zip(ammo.items, ammo_count)]
    resources.extend(
        (resource_database.get_item(item), count)
        for item, count in ammo.additional_resources.items()
    )

    return PickupEntry(
        name=ammo.name,
        progression=(),
        extra_resources=tuple(resources),
        model=PickupModel(
            game=resource_database.game_enum,
            name=ammo.model_name,
        ),
        pickup_category=ammo.pickup_category,
        broad_category=ammo.broad_category,
        respects_lock=requires_main_item,
        resource_lock=ammo.create_resource_lock(resource_database),
        generator_params=PickupGeneratorParams(
            preferred_location_category=ammo.preferred_location_category,
            probability_multiplier=2,
        ),
    )


def create_nothing_pickup(resource_database: ResourceDatabase) -> PickupEntry:
    """
    Creates a Nothing pickup.
    :param resource_database:
    :return:
    """
    return PickupEntry(
        name="Nothing",
        progression=(
            (resource_database.get_item_by_name("Nothing"), 1),
        ),
        model=PickupModel(
            game=resource_database.game_enum,
            name="Nothing",
        ),
        pickup_category=pickup_category.USELESS_PICKUP_CATEGORY,
        broad_category=pickup_category.USELESS_PICKUP_CATEGORY,
        generator_params=PickupGeneratorParams(
            preferred_location_category=LocationCategory.MAJOR,  # TODO
        ),
    )


def create_visual_etm() -> PickupEntry:
    """
    Creates an ETM that should only be used as a visual pickup.
    :return:
    """
    return PickupEntry(
        name="Unknown item",
        progression=(),
        model=PickupModel(
            game=RandovaniaGame.METROID_PRIME_ECHOES,
            name=echoes_items.USELESS_PICKUP_MODEL,
        ),
        pickup_category=pickup_category.USELESS_PICKUP_CATEGORY,
        broad_category=pickup_category.USELESS_PICKUP_CATEGORY,
        generator_params=PickupGeneratorParams(
            preferred_location_category=LocationCategory.MAJOR,  # TODO
        ),
    )
